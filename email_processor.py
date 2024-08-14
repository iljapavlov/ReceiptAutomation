import pandas as pd
from collections import defaultdict
import imaplib
import email
from email.header import decode_header
import os
from dotenv import load_dotenv
import re
from bs4 import BeautifulSoup

class EmailProcessor:
    def __init__(self):
        load_dotenv()
        self.imap_server = os.getenv("IMAP_SERVER")
        self.email_address = os.getenv("EMAIL_ADDRESS")
        self.password = os.getenv("EMAIL_PASSWORD")
        self.imap_connection = None
        self.filters = [
            {"sender": "noreply.tsekk@maxima.ee", "subject": "Sinu ostutšekk!"},
            {"sender": "noreply@rimibaltic.com", "subject": "Sinu ostutšekk"},
            {"sender": "estonia-food@bolt.eu", "subject": "Delivery from Bolt Food"}
        ]

    def connect(self):
        try:
            self.imap_connection = imaplib.IMAP4_SSL(self.imap_server)
            self.imap_connection.login(self.email_address, self.password)
            print("Connected successfully to the IMAP server.")
        except imaplib.IMAP4.error as e:
            print(f"IMAP login failed: {e}")
        except ConnectionRefusedError as e:
            print(f"Connection refused: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

    def disconnect(self):
        if self.imap_connection:
            self.imap_connection.logout()

    def get_filtered_emails(self):
        self.imap_connection.select("INBOX")
        filtered_emails = defaultdict(list)

        for filter_criteria in self.filters:
            sender = filter_criteria["sender"]
            subject = filter_criteria["subject"]
            
            _, message_numbers = self.imap_connection.search(None, f'FROM "{sender}"')
            
            for num in message_numbers[0].split():
                _, msg_data = self.imap_connection.fetch(num, '(RFC822)')
                email_body = msg_data[0][1]
                email_message = email.message_from_bytes(email_body)
                
                email_subject, encoding = decode_header(email_message["Subject"])[0]
                if isinstance(email_subject, bytes):
                    email_subject = email_subject.decode(encoding or "utf-8")
                
                if email_subject == subject:
                    email_sender = email_message["From"]
                    email_date = email_message["Date"]
                    
                    content = self.get_email_content(email_message)
                    
                    filtered_emails[sender].append({
                        "subject": email_subject,
                        "sender": email_sender,
                        "date": email_date,
                        "content": content
                    })

        return filtered_emails

    def get_email_content(self, email_message):
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() in ["text/plain", "text/html"]:
                    return part.get_payload(decode=True).decode(errors='replace')
        else:
            return email_message.get_payload(decode=True).decode(errors='replace')

    def parse_emails(self, filtered_emails):
        parsed_data = []
        for sender, emails in filtered_emails.items():
            for email_data in emails:
                if "maxima.ee" in sender:
                    parsed_data.append(self.parse_maxima_email(email_data))
                elif "rimibaltic.com" in sender:
                    parsed_data.append(self.parse_rimi_email(email_data))
                elif "bolt.eu" in sender:
                    parsed_data.append(self.parse_bolt_email(email_data))
        return parsed_data

    def parse_maxima_email(self, email_data):
        soup = BeautifulSoup(email_data['content'], 'html.parser')
        items = []
        items_table = soup.find('div', id='linestable')
        for row in items_table.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) == 3:
                item = {
                    "name": cells[0].text.strip(),
                    "quantity": cells[1].text.strip(),
                    "price": cells[2].text.strip()
                }
                items.append(item)
        
        total_price = soup.find('tr', class_='totalPrice')
        total = total_price.find_all('td')[1].text.strip() if total_price else None

        payment_method = "Card" if soup.find(string=re.compile("Makstud Pangakaardiga")) else None

        return {
            "date": email_data['date'],
            "store": "Maxima",
            "address": "Placeholder", # TODO implement
            "items": items,
            "total": total,
            "payment_method": payment_method
        }

    def parse_rimi_email(self, email_data):
        soup = BeautifulSoup(email_data['content'], 'html.parser')
        # Assuming similar structure as Maxima
        items = []
        return {
            "date": email_data['date'],
            "store": "Rimi",
            "address": None,
            "items": items, # Should be filled with actual parsing
            "total": None,  # Same here
            "payment_method": None
        }

    def parse_bolt_email(self, email_data):
        soup = BeautifulSoup(email_data['content'], 'html.parser')
        items = []
        items_table = soup.find('table', class_='header')
        for row in items_table.find_all('tr'):
            item_name = row.find('span', style="color: #2f313f; font-size: 16px; line-height: 24px;")
            if item_name:
                item = {
                    "name": item_name.text.strip(),
                    "quantity": row.find('span', style="display: inline-block; color: #2f313f; font-size: 16px; line-height: 24px;").text.strip(),
                    "price": row.find('p', style="display: inline-block; color: #2f313f; font-size: 16px; line-height: 24px;").text.strip()
                }
                items.append(item)

        total = soup.find('p', string="Total charged:").find_next('p').text.strip()
        payment_method = "Mastercard" if soup.find('img', src=re.compile("mc-2x.png")) else None

        return {
            "date": email_data['date'],
            "store": soup.find(string="From").find_next('span').text.strip(),
            "address": soup.find(string="From").find_next('a', class_='address-title').text.strip(),
            "items": items,
            "total": total,
            "payment_method": payment_method
        }

    def to_dataframe(self, parsed_emails):
        records = []
        for email in parsed_emails:
            for item in email['items']:
                record = {
                    "date": email.get('date'),
                    "store": email.get('store'),
                    "address": email.get('address'),
                    "item_name": item.get('name'),
                    "item_quantity": item.get('quantity'),
                    "item_price": item.get('price'),
                    "total": email.get('total'),
                    "payment_method": email.get('payment_method')
                }
                records.append(record)

        df = pd.DataFrame(records)
        return df

if __name__ == "__main__":
    processor = EmailProcessor()
    processor.connect()
    filtered_emails = processor.get_filtered_emails()
    parsed_emails = processor.parse_emails(filtered_emails)
    df = processor.to_dataframe(parsed_emails)
    processor.disconnect()

    # Display the DataFrame
    print(df)
    df.to_csv('output.csv')
