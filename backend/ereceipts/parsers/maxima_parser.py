from bs4 import BeautifulSoup
import pandas as pd
import pandas as pd
import difflib

def maxima_parser(html_content, verbose = False):
    soup = BeautifulSoup(html_content, 'html.parser')

    # General INFO
    receipt_table = soup.find_all("table", {"class": "receipt_table"})[0]
    store_info = receipt_table.find_all('tr')[4].text.strip()
    total_price = float(soup.find('tr', {'class': 'totalPrice'}).find_all('td')[1].text.strip().replace('€', '').replace(',', '.'))
    location = store_info.split('\n')[1].strip()

    dtime_info = soup.find_all("div", {'id':'Footer'})[0].find_all("tr")[-1] # dtime in footer
    dtime_info = dtime_info.find_all('td')[-1].text.strip()         

    # Product INFO
    payments_table = soup.find('div', {'id':'payments'})

    # product name, quantity, price, and price after discount
    products = []
    lines = soup.find_all('tr')
    for line in lines:
        cells = line.find_all('td')
        if len(cells) == 3:
            product_name = cells[0].text.strip()
            quantity_and_price = cells[1].text.strip().split(' × ')
            quantity, quantity_unit = 1, 'pc'
            if len(quantity_and_price)>1:
                if 'kg' in quantity_and_price[1]:
                    quantity_unit = 'kg'
                    quantity = float(quantity_and_price[1].replace('kg',''))
                else:
                    quantity_unit = 'pc'
                    quantity = int(quantity_and_price[1])

            price = float(cells[2].text.strip().replace('€', '').replace(',', '.'))
            products.append({
                'name': product_name,
                'quantity': quantity,
                'quantity unit':quantity_unit,
                'price': price
            })
        elif len(cells) == 2 and 'Discount' in cells[0].text:
            discount = float(cells[1].text.strip().replace('€', '').replace('-', '').replace(',', '.'))
            products[-1]['discount'] = discount
    products = pd.DataFrame(products)

    # Additional info from Discount product section
    payments_table = soup.find('div', {'id':'payments'})
    totalDiscounts = payments_table.find('tr', {'id':'totalDiscounts'})
    ids_to_filter = ['aitahCard', 'receivedMaximaMoney', 'MaximaMoneyBalance']
    all_trs_in_payments = payments_table.find_all('tr')
    discounted_products = []
    start_collecting = False
    for tr in all_trs_in_payments:
        if tr == totalDiscounts:
            start_collecting = True
            continue
        if start_collecting:
            if tr.attrs.get('id') not in ids_to_filter:
                discounted_products.append(tr)
    discount_product_list = []

    for product in discounted_products:
        product_info = product.find_all('td')
        if len(product_info) == 2:
            name = product_info[0].text.strip()
            discount = float(product_info[1].text.strip().replace('€', '').replace(',', '.'))
            discount_product_list.append({'name':name, 'discount':discount})
    discount_product_list = pd.DataFrame(discount_product_list)


    # Merge discount and product list
    def find_best_match(product_name, products):
        # function to find the best match in the products based on name
        matches = difflib.get_close_matches(product_name, products['name'], n=1, cutoff=0.1)
        return matches[0] if matches else None

    discount_product_list['matched_name'] = discount_product_list['name'].apply(lambda x: find_best_match(x, products))

    merged_df = pd.merge(
        products,
        discount_product_list,
        left_on=['name', 'discount'],
        right_on=['matched_name', 'discount'],
        how='left',
        suffixes=('_products', '_discounted')
    )

    merged_df.drop(columns=['matched_name'], inplace=True)


    # show all the info
    if verbose:
        print('General info:')
        print(f"Store Location: {location}")
        print(f"Total Price: {total_price} €")

    output = {
        'location':location,
        'total':total_price,
        'dtime':dtime_info,
        'products':merged_df
    }

    return output