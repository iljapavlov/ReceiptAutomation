from flask import Flask, request, jsonify
import pandas as pd
import json
from flask_cors import CORS
from categories import categories
from preprocessing import *
from utils import load_csv

app = Flask(__name__)
CORS(app)

expense_mapping, income_mapping = load_mapping_tables()


@app.route('/upload_statement', methods=['POST'])
def upload_statement():
    global df
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and file.filename.endswith('.csv'):
        df = load_csv(file)
        df = preprocess_data(df)
        insights = generate_insights(df)
        return jsonify(insights)
    
    return jsonify({'error': 'Invalid file format'}), 400

@app.route('/get_next_partners', methods=['GET'])
def get_next_partners():
    total_partners = df['PARTNER'].nunique()
    categorized_partners = len(set(expense_mapping.keys()) | set(income_mapping.keys()))
    
    # Group by partner and transaction type, calculate total absolute sum
    partner_sums = df.groupby(['PARTNER', 'is_expense'])['SUM'].sum().abs().reset_index()
    partner_sums = partner_sums.sort_values('SUM', ascending=False)

    next_partners = []
    for _, row in partner_sums.iterrows():
        partner = row['PARTNER']
        is_expense = row['is_expense']
        
        if (is_expense and partner not in expense_mapping) or (not is_expense and partner not in income_mapping):
            partner_info = create_partner_info(df[df['PARTNER'] == partner].iloc[0], is_expense, categorized_partners, total_partners)
            next_partners.append(partner_info)
            
        if len(next_partners) == 10:  # Pre-load 10 partners
            break
    
    return jsonify(next_partners)

@app.route('/get_insights', methods=['GET'])
def get_insights():
    insights = generate_insights(df)
    return jsonify(insights)

@app.route('/get_categories', methods=['GET'])
def get_categories():
    return jsonify(categories)

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

if __name__ == '__main__':
    app.run(debug=True)