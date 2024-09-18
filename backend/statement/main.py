from flask import Flask, request, jsonify
import pandas as pd
import json
from flask_cors import CORS
from categories import categories
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import io
import base64

app = Flask(__name__)
CORS(app)


# Load and preprocess the CSV file
def map_category(row):
    partner = row['PARTNER']
    is_expense = row['is_expense']
    if is_expense:
        return expense_mapping.get(partner, 'Uncategorized')
    else:
        return income_mapping.get(partner, 'Uncategorized')
        
def preprocess_data(df):
    df = df.drop(columns=['Transfer reference', 'Document number', 'Unnamed: 12', 'Row type','Reference number','Client account'])

    # convert types
    df['Amount'] = df['Amount'].str.replace(',', '.').astype(float)
    df['Date'] = pd.to_datetime(df['Date'], format='%d.%m.%Y')
    df = df.fillna({'Beneficiary/Payer':'','Details':'','Amount':0})

    df['Debit/Credit'] = df['Debit/Credit'].map({'K': False, 'D': True})
    df = df.rename(columns={'Debit/Credit':'is_expense', 'Details': 'INFO','Beneficiary/Payer':'PARTNER', 'Amount':'SUM'})

    df['Category'] = df.apply(map_category, axis=1)

    # preprocessing
    df_extra = df[df['Transaction type'].isin(['LS','AS','K2','M'])].copy()
    df_main = df[~df.index.isin(df_extra.index)].copy()
    df_main.loc[df_main.is_expense,'SUM'] = df_main.loc[df_main.is_expense,'SUM']*(-1)

    # add features
    df_main['family_transfer'] = df_main['PARTNER'].str.lower().str.contains('pavlov')

    return df_main

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

@app.route('/upload_statement', methods=['POST'])
def upload_statement():
    global df
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and file.filename.endswith('.csv'):
        df = pd.read_csv(file, sep=';')
        df = preprocess_data(df)
        insights = generate_insights(df)
        return jsonify(insights)
    
    return jsonify({'error': 'Invalid file format'}), 400

@app.route('/get_insights', methods=['GET'])
def get_insights():
    insights = generate_insights(df)
    return jsonify(insights)

def generate_insights(df):
    global expense_mapping, income_mapping
    expense_mapping, income_mapping = load_mapping_tables()

    df['Category'] = df.apply(map_category, axis=1)

    # Calculate various statistics and generate plots
    total_transactions = len(df)
    total_income = df[df['SUM'] > 0]['SUM'].sum()
    total_expenses = abs(df[df['SUM'] < 0]['SUM'].sum())
    net_balance = total_income - total_expenses
    avg_transaction = df['SUM'].mean()
    largest_expense = abs(df[df['SUM'] < 0]['SUM'].min())
    largest_income = df[df['SUM'] > 0]['SUM'].max()
    expense_ratio = total_expenses / total_income if total_income > 0 else 0
    
    # Top 5 expense categories
    top_expense_categories = df[df['SUM'] < 0].groupby('Category')['SUM'].sum().sort_values().head().to_dict()
    
    # Generate category distribution plot
    plt.figure(figsize=(10, 6))
    df['Category'].value_counts().plot(kind='pie')
    plt.title('Transactions by Category')
    category_distribution = plot_to_base64(plt)
    
    # Generate monthly spending trend plot
    df['Date'] = pd.to_datetime(df['Date'])
    monthly_trend = df.groupby(df['Date'].dt.to_period('M'))['SUM'].sum()
    plt.figure(figsize=(12, 6))
    monthly_trend.plot(kind='line')
    plt.title('Monthly Spending Trend')
    monthly_trend_plot = plot_to_base64(plt)
    
    # Generate average spending by weekday plot
    weekday_spending = df[df['SUM'] < 0].groupby(df['Date'].dt.dayofweek)['SUM'].mean()
    plt.figure(figsize=(10, 6))
    weekday_spending.plot(kind='bar')
    plt.title('Average Spending by Weekday')
    plt.xlabel('Weekday')
    plt.ylabel('Average Spending')
    weekday_spending_plot = plot_to_base64(plt)
    
    # # Generate average spending by hour plot
    # hourly_spending = df[df['SUM'] < 0].groupby(df['Date'].dt.hour)['SUM'].mean()
    # plt.figure(figsize=(12, 6))
    # hourly_spending.plot(kind='line')
    # plt.title('Average Spending by Hour')
    # plt.xlabel('Hour of Day')
    # plt.ylabel('Average Spending')
    # hourly_spending_plot = plot_to_base64(plt)
    
    return {
        'total_transactions': total_transactions,
        'total_income': total_income,
        'total_expenses': total_expenses,
        'net_balance': net_balance,
        'avg_transaction': avg_transaction,
        'largest_expense': largest_expense,
        'largest_income': largest_income,
        'expense_ratio': expense_ratio,
        'top_expense_categories': [{'name': k, 'amount': v} for k, v in top_expense_categories.items()],
        'category_distribution': category_distribution,
        'monthly_trend': monthly_trend_plot,
        'weekday_spending': weekday_spending_plot,
        # 'hourly_spending': hourly_spending_plot
    }

def plot_to_base64(plt):
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    plt.close()
    return image_base64

def create_partner_info(row, is_expense, categorized_partners, total_partners):
    partner = row['PARTNER']
    partner_df = df[(df['PARTNER'] == partner) & (df['is_expense'] == is_expense)]
    
    # Filter out NaN values from the 'SUM' column
    sum_data = partner_df['SUM'].dropna()

    # Calculate the optimal number of bins for the histogram
    num_bins = (sum_data.shape[0]+1)//2

    plt.style.use('dark_background')  # Set the dark background theme
    sns.set_palette("coolwarm")  # Use a cool/warm color palette
    plt.figure(figsize=(8, 4))
    
    # hist
    sns.histplot(sum_data, bins=num_bins, kde=True, color="skyblue", edgecolor='black')

    # Calculate and plot the mean, ignoring NaN values
    mean_value = sum_data.mean()
    plt.axvline(mean_value, color='red', linestyle='dashed', linewidth=2)

    # Annotate the mean value on the plot
    plt.text(mean_value - .2, plt.gca().get_ylim()[1] * 0.8, f'{mean_value:.2f}', 
             color='red', ha='center', va='bottom', fontsize=12, fontweight='bold', rotation=90)

    # Add labels and title
    plt.xlabel('Amount', fontsize=12)
    plt.ylabel('Frequency', fontsize=12)

    plt.tight_layout()

    # Convert plot to base64 string
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    plot_data = base64.b64encode(buffer.getvalue()).decode()
    plt.close()

    return {
        "partner": partner,
        "transaction_count": len(partner_df),
        "is_expense": is_expense,
        "most_popular_info": partner_df['INFO'].mode().iloc[0],
        "progress": f"{categorized_partners}/{total_partners}",
        "price_distribution": plot_data
    }

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