from flask import Flask, request, jsonify
import pandas as pd
import json
from flask_cors import CORS
from categories import categories
import matplotlib.pyplot as plt
import io
import base64

app = Flask(__name__)
CORS(app)


# Load and preprocess the CSV file
def load_and_preprocess_data():
    df = pd.read_csv('./data/statement.csv', sep=';')
    df = df.drop(columns=['Transfer reference', 'Document number', 'Unnamed: 12', 'Row type','Reference number','Client account'])

    # convert types
    df['Amount'] = df['Amount'].str.replace(',', '.').astype(float)
    df['Date'] = pd.to_datetime(df['Date'], format='%d.%m.%Y')
    df = df.fillna({'Beneficiary/Payer':'','Details':'','Amount':0})

    df['Debit/Credit'] = df['Debit/Credit'].map({'K': False, 'D': True})
    df = df.rename(columns={'Debit/Credit':'is_expense', 'Details': 'INFO','Beneficiary/Payer':'PARTNER', 'Amount':'SUM'})

    # preprocessing
    df_extra = df[df['Transaction type'].isin(['LS','AS','K2','M'])].copy()
    df_main = df[~df.index.isin(df_extra.index)].copy()
    df_main.loc[df_main.is_expense,'SUM'] = df_main.loc[df_main.is_expense,'SUM']*(-1)

    # add features
    df_main['family_transfer'] = df_main['PARTNER'].str.lower().str.contains('pavlov')

    return df_main

df = load_and_preprocess_data()

# Load mapping tables
def load_mapping_tables():
    try:
        with open('./data/expense_mapping.json', 'r') as f:
            expense_mapping = json.load(f)
    except FileNotFoundError:
        expense_mapping = {}

    try:
        with open('./data/income_mapping.json', 'r') as f:
            income_mapping = json.load(f)
    except FileNotFoundError:
        income_mapping = {}

    return expense_mapping, income_mapping

expense_mapping, income_mapping = load_mapping_tables()

@app.route('/get_next_partner', methods=['GET'])
def get_next_partner():
    total_partners = df['PARTNER'].nunique()
    categorized_partners = len(set(expense_mapping.keys()) | set(income_mapping.keys()))
    
    for _, row in df.iterrows():
        partner = row['PARTNER']
        is_expense = row['is_expense']
        
        if is_expense and partner not in expense_mapping:
            return create_partner_info(row, is_expense, categorized_partners, total_partners)
        elif not is_expense and partner not in income_mapping:
            return create_partner_info(row, is_expense, categorized_partners, total_partners)
    
    return jsonify({"message": "All partners categorized"})

def create_partner_info(row, is_expense, categorized_partners, total_partners):
    partner = row['PARTNER']
    partner_df = df[df['PARTNER'] == partner]
    print(partner_df['SUM'])
    return jsonify({
        "partner": partner,
        "avg_amount": partner_df['SUM'].mean(),
        "std_amount": partner_df['SUM'].std() if partner_df['SUM'].shape[0] > 1 else 0,
        "max_amount": partner_df['SUM'].max(),
        "min_amount": partner_df['SUM'].min(),
        "transaction_count": len(partner_df),
        "is_expense": is_expense,
        "most_popular_info": partner_df['INFO'].mode().iloc[0],
        "progress": f"{categorized_partners}/{total_partners}"
    })

@app.route('/categorize', methods=['POST'])
def categorize():
    data = request.json
    partner = data['partner']
    category = data['category']
    subcategory = data['subcategory']
    is_expense = data['is_expense']

    if is_expense:
        expense_mapping[partner] = f"{category} - {subcategory}"
        with open('./data/expense_mapping.json', 'w') as f:
            json.dump(expense_mapping, f)
    else:
        income_mapping[partner] = f"{category} - {subcategory}"
        with open('./data/income_mapping.json', 'w') as f:
            json.dump(income_mapping, f)

    return jsonify({"message": "Categorization saved successfully"})

@app.route('/get_categories', methods=['GET'])
def get_categories():
    return jsonify(categories)

if __name__ == '__main__':
    app.run(debug=True)