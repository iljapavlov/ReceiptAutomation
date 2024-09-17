import re
import pandas as pd
import numpy as np
from scipy.stats import zscore
import cv2
import pytesseract
from pdf2image import convert_from_bytes

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def crop_from(image, side='right', percentage=0.15):
    height, width = image.shape[:2]
    crop_width = int(width * percentage)
    if side=='right':
        cropped_image = image[:, width - crop_width:]
    elif side == 'left':
        cropped_image = image[:, : 1 - (width - crop_width)]
    return cropped_image

def parse_product_list(text):
    # Split text into lines
    lines = text.splitlines()

    products = []
    current_product = {}
    price_pattern = re.compile(r'\d+,\d{2}\s\w')  # Pattern to match prices like 3,19 G

    for line in lines:
        line = line.strip()

        # Check if line is a price
        if price_pattern.search(line):
            current_product['price'] = price_pattern.search(line).group()
            products.append(current_product)
            current_product = {}
        elif line.startswith('Allah.'):
            # It's a discount line, skip or store as needed
            current_product['discount'] = line
        else:
            # It's part of the product description
            if 'name' not in current_product:
                current_product['name'] = line
            else:
                current_product['name'] += ' ' + line

    # products = [p for p in products if 'name' in p.keys()]
    return products

def filter_price_info(price_info):
    price_info['area'] = price_info['width'] * price_info['height']
    price_info['zscore'] = zscore(price_info['area'])
    outlier_threshold = 0.4

    price_info_filtered = price_info[abs(price_info['zscore']) < outlier_threshold].copy()
    price_info_filtered.drop(columns=['area', 'zscore'], inplace=True)
    price_info_filtered = price_info_filtered[price_info_filtered.conf!=-1]
    return price_info_filtered.reset_index(drop=True)

def filter_discounts(df):
    name_info = df.copy()
    name_info = name_info[name_info['text'].str.contains('Allah.')]
    return name_info.reset_index(drop=True)

def group_words_into_lines(df, epsilon=15):
    """
    Groups words into lines based on their vertical positions.
    """
    # Sort by top to help with grouping
    df = df.sort_values(by='top').reset_index(drop=True)
    
    # Initialize line grouping
    line_groups = []
    current_line = []
    current_top = df.iloc[0]['top']
    
    for _, row in df.iterrows():
        # If the word is within epsilon distance in vertical position, consider it the same line
        if abs(row['top'] - current_top) <= epsilon:
            current_line.append(row)
        else:
            # Move to the next line
            line_groups.append(pd.DataFrame(current_line))
            current_line = [row]
            current_top = row['top']
    
    # Append the last line
    if current_line:
        line_groups.append(pd.DataFrame(current_line))
    
    return line_groups

def concatenate_text_in_region(df, epsilon=15):
    """
    Concatenates text within each region, ordering words correctly within lines and lines within regions.
    """
    # Group by region index
    concatenated_texts = []
    
    for region_index, group in df.groupby('region_index'):
        # Group words into lines
        lines = group_words_into_lines(group, epsilon)

        # Sort words within each line by their left (x) position
        lines = [line.sort_values(by='left') for line in lines]
        
        # Sort lines by their top (y) position
        lines = sorted(lines, key=lambda x: x['top'].mean())
        
        # Concatenate words in each line
        concatenated_lines = [' '.join(line['text'].tolist()) for line in lines]
        
        # Concatenate all lines in the region
        region_text = ' '.join(concatenated_lines)
        
        # Store result with region index
        concatenated_texts.append({'region_index': region_index, 'concatenated_text': region_text})
    
    return pd.DataFrame(concatenated_texts)

def parse_product_line(line):
    # Regular expressions for detecting quantities
    weight_pattern = re.compile(r'(\d+(?:,\d+)?)\s*(g|kg)')
    piece_pattern = re.compile(r'(\d+(?:,\d+)?)\s*tk')
    price_pattern = re.compile(r'X\s*(\d+,\d+)\s')

    # Initialize extracted data
    product_name = line
    quantity = None
    quantity_units = None

    # Detect weight
    weight_match = weight_pattern.search(line)
    if weight_match:
        weight_value = float(weight_match.group(1).replace(',', '.'))
        weight_unit = weight_match.group(2)
        
        if weight_unit == 'kg':
            weight_value *= 1000  # Convert kg to grams
        
        quantity = weight_value
        quantity_units = 'g'

    # Detect pieces
    piece_match = piece_pattern.search(line)
    if piece_match:
        piece_count = float(piece_match.group(1).replace(',', '.'))
        
        if quantity_units == 'g':
            # Multiply grams by number of pieces
            quantity *= piece_count
        else:
            quantity = piece_count
            quantity_units = 'pieces'
    
    # Remove the quantity and unit information from the product name
    product_name = re.sub(weight_pattern, '', product_name)
    product_name = re.sub(piece_pattern, '', product_name)
    product_name = re.sub(price_pattern, '', product_name)

    # Clean up the product name by stripping extra spaces
    product_name = product_name.strip()
    
    return product_name, quantity, quantity_units


class RimiParser():
    def __init__(self, attachments):
        pdf_io = [a for a in attachments if a['content-type'] == 'application/pdf'][0]['content']
        pdf_io.getvalue()

        # use ocr
        images = convert_from_bytes(pdf_io.getvalue(), poppler_path=r'C:/Program Files/poppler-24.07.0/Library/bin')
        self.image = np.array(images[0]) # TODO there could be multiple attachemnts?
        self.price_product_thr = 0.75 # vertical line to separate prices

    def run(self):
        self.detect_dashed_regions()

        self.roi_list = {
            'store_info': (0,self.dashed_lines[0]),
            'product_list': (self.dashed_lines[1],self.dashed_lines[2]),
            'total_info': (self.dashed_lines[-1],self.image.shape[0])
        }
        # process each region of interest separately
        results = {}
        for section_name, (start_y, end_y) in self.roi_list.items():
            roi = self.image[start_y:end_y, :]

            if section_name == 'store_info':
                text = pytesseract.image_to_string(roi)
                results['location'] = self.parse_store_info(text)
            elif section_name == 'product_list':
                results['products'] = self.detect_products(roi)
            elif section_name == 'total_info':
                text = pytesseract.image_to_string(roi)
                results['dtime'] = self.parse_total_info(text)

        return results

    def detect_dashed_regions(self):
        gray = cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 1)) # horizontal line
        morph = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=2)

        imgLines= cv2.HoughLinesP(morph, 10, np.pi/180, 20, minLineLength = 440, maxLineGap = 15)

        if len(imgLines) == 0:
            raise RuntimeError('No dashed lines detected')

        self.dashed_lines = [int((line[0][1]+line[0][3])/2) for line in imgLines]
        self.dashed_lines = sorted(self.dashed_lines)

    def parse_store_info(self, text):
        # Find the address lines by splitting the text and looking for patterns
        lines = text.splitlines()
        address_lines = []
        store_info_start = False
        
        for line in lines:
            if "KMKNR" in line:
                store_info_start = True
                continue
            if store_info_start:
                if "www" in line:
                    break
                if line.strip():
                    address_lines.append(line.strip())

        return ', '.join(address_lines)
    
    def detect_products(self, roi):
        # split image in two part to detect discounted items on the left and prices on the right
        price_section = crop_from(roi, side='right',percentage=1-self.price_product_thr)
        name_section = crop_from(roi, side='left',percentage=self.price_product_thr)

        self.price_info =  pytesseract.image_to_data(price_section, output_type='dict', config='--psm 11')
        self.price_info = pd.DataFrame(self.price_info)
        print(self.price_info)
        self.price_info = filter_price_info(self.price_info)
        print(self.price_info)
        
        self.name_info = pytesseract.image_to_data(name_section, output_type='dict')
        self.name_info = pd.DataFrame(self.name_info)
        self.name_info = self.name_info[self.name_info['conf']!=-1]
        discount_info = filter_discounts(self.name_info)

        # save raw detections for vizualization
        self.raw_name_info = self.name_info.copy()
        self.raw_price_info = self.price_info.copy()

        product_borders = []
        for ind,row in discount_info.iterrows():
            (x, y, w, h) = (row['left'], row['top'], row['width'], row['height'])
            product_borders.append({'type':'name','y':y+h})

        for ind,row in self.price_info.iterrows():
            (x, y, w, h) = (row['left'], row['top'], row['width'], row['height'])
            product_borders.append({'type':'price','y':y+h})

        product_borders = pd.DataFrame(product_borders)
        product_borders = product_borders.sort_values(by='y', ascending = True).drop_duplicates(subset=['type','y']).reset_index(drop=True)

        # product borders refinement
        self.new_product_borders = []

        product_start = True
        for ind, row in product_borders.iterrows():
            if ind != product_borders.shape[0]-1:
                if product_start and row['type'] == 'price' and product_borders.loc[ind+1, 'type'] == 'price':
                    product_start = False
                elif product_start and row['type'] == 'name':
                    product_start = False
            else:
                product_start = False
            
            if not product_start:
                # product border detected
                self.new_product_borders.append(row['y'])
                product_start = True

        self.new_product_borders = [0] + self.new_product_borders + [roi.shape[0]]
        self.new_product_borders = sorted(list(set(self.new_product_borders)))

        # group info based on the detected product borders
        self.name_info['y_average'] = self.name_info['top'] + self.name_info['height']/2
        self.price_info['y_average'] = self.price_info['top'] + self.price_info['height']/2

        self.price_info['region_index'] = pd.cut(
            self.price_info['y_average'],
            bins=self.new_product_borders,
            labels=False,
            include_lowest=True 
        )

        self.name_info['region_index'] = pd.cut(
            self.name_info['y_average'],
            bins=self.new_product_borders,
            labels=False,
            include_lowest=True 
        )

        # concat text from the same regions
        self.price_info = concatenate_text_in_region(self.price_info, epsilon=10)
        self.name_info = concatenate_text_in_region(self.name_info, epsilon=30)

        total_info = self.name_info.merge(self.price_info, how='left', on='region_index')
        total_info.columns = ['region_index', 'name', 'price']

        total_info['name'] = total_info['name'].str.replace(r'\s+', ' ', regex=True)
        total_info['name'] = total_info['name'].str.replace(r'Allah\..*', '', regex=True)

        # cleaned up products
        products = []
        for name in total_info['name'].values:
            product_name, quantity, quantity_units = parse_product_line(name)
            products.append({
                'name': product_name,
                'quantity': quantity,
                'quantity units': quantity_units,
            })

        return total_info
    
    def parse_total_info(self, text):
        datetime_match = re.search(r'KUUPAEV:\s*(\d{2}\.\d{2}\.\d{4})\s+AEG:\s*(\d{2}:\d{2}:\d{2})', text)
        if datetime_match:
            date = datetime_match.group(1)
            time = datetime_match.group(2)
            return f"{date} {time}"
        return None

    def vizualize(self):
        self.viz = self.image.copy()
        new_width = self.viz.shape[1] + 150

        extended_viz = np.zeros((self.viz.shape[0], new_width, 3), dtype=np.uint8)
        extended_viz[:, :self.viz.shape[1]] = self.viz

        # Annotate the dashed lines
        for line in self.dashed_lines:
            cv2.line(extended_viz, (self.viz.shape[1] - 50, line), (self.viz.shape[1], line), (0, 255, 0), thickness=2)
            # cv2.putText(extended_viz, "dashed line", (self.viz.shape[1] + 10, line + 5), 
            #             cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA)
            
        # Annotate product borders
        product_section_top = self.roi_list['product_list'][0]
        product_section_bottom = self.roi_list['product_list'][1]

        for border in self.new_product_borders:
            cv2.line(extended_viz, (0, product_section_top + border), (self.viz.shape[1], product_section_top + border), (255, 0, 0), thickness=1)
            cv2.putText(extended_viz, "product border", (self.viz.shape[1] + 10, product_section_top + border + 5), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA)
            
        cv2.line(extended_viz, (int(self.price_product_thr*self.viz.shape[1]), product_section_top), (int(self.price_product_thr*self.viz.shape[1]), product_section_bottom), (255,0,0), thickness=1)
            
        alpha = 0.2
        overlay = extended_viz.copy()
        for _, row in self.raw_name_info.iterrows():
            x, y, w, h = row['left'], row['top'], row['width'], row['height']
            cv2.rectangle(overlay, 
                        (x, product_section_top + y), 
                        (x + w, product_section_top + y + h), 
                        (0, 255, 0), -1)  # -1 fills the rectangle

        for _, row in self.raw_price_info.iterrows():
            x, y, w, h = row['left'], row['top'], row['width'], row['height']
            cv2.rectangle(overlay, 
                        (int(self.viz.shape[1] * self.price_product_thr) + x, product_section_top + y), 
                        (int(self.viz.shape[1] * self.price_product_thr) + x + w, product_section_top + y + h), 
                        (0, 255, 0), -1)  # -1 fills the rectangle

        cv2.addWeighted(overlay, alpha, extended_viz, 1 - alpha, 0, extended_viz)
        return extended_viz

