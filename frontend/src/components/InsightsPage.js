import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './InsightsPage.css';

function formatNumberWithSpaces(number) {
    const numberString = number.toFixed(2); // Ensure two decimal places
    const [integerPart, decimalPart] = numberString.split('.');
    const formattedIntegerPart = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
    return decimalPart ? `${formattedIntegerPart}.${decimalPart}` : formattedIntegerPart;
  }
  
function InsightsPage({ onCategorize, statementData, setStatementData }) {
  const [file, setFile] = useState(null);

  useEffect(() => {
    if (statementData) {
      refreshInsights();
    }
  }, []); // This will run when the component mounts or when returning from categorizer

  const refreshInsights = async () => {
    try {
      const response = await axios.get('http://localhost:5000/get_insights');
      setStatementData(response.data);
    } catch (error) {
      console.error('Error refreshing insights:', error);
    }
  };

  const handleFileUpload = async (event) => {
    const uploadedFile = event.target.files[0];
    setFile(uploadedFile);

    const formData = new FormData();
    formData.append('file', uploadedFile);

    try {
      const response = await axios.post('http://localhost:5000/upload_statement', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setStatementData(response.data);
    } catch (error) {
      console.error('Error uploading file:', error);
    }
  };

  const renderDashboard = () => {
    if (!statementData) return null;

    const summaryItems = [
        { label: 'Total Transactions', value: statementData.total_transactions },
        { label: 'Total Income', value: `€${formatNumberWithSpaces(statementData.total_income)}` },
        { label: 'Total Expenses', value: `€${formatNumberWithSpaces(statementData.total_expenses)}` },
        { label: 'Net Balance', value: `€${formatNumberWithSpaces(statementData.net_balance)}` },
        { label: 'Average Transaction', value: `€${formatNumberWithSpaces(statementData.avg_transaction)}` },
        { label: 'Largest Expense', value: `€${formatNumberWithSpaces(statementData.largest_expense)}` },
        { label: 'Largest Income', value: `€${formatNumberWithSpaces(statementData.largest_income)}` },
        { label: 'Expense Ratio', value: `${(statementData.expense_ratio * 100).toFixed(2)}%` },
      ];

    return (
      <div className="dashboard">
        <div className="summary-grid">
          {summaryItems.map((item, index) => (
            <div key={index} className="summary-item">
              <div className="summary-value">{item.value}</div>
              <div className="summary-label">{item.label}</div>
            </div>
          ))}
        </div>
        <div className="pie-chart">
          <h3>Spending by Category</h3>
          <img src={`data:image/png;base64,${statementData.category_distribution}`} alt="Category Distribution" />
        </div>
      </div>
    );
  };

  const renderInsights = () => {
    if (!statementData) return null;

    return (
      <div className="insights-grid">
        <div className="insight-card">
          <h3>Monthly Spending Trend</h3>
          <img src={`data:image/png;base64,${statementData.monthly_trend}`} alt="Monthly Spending Trend" />
        </div>
        <div className="insight-card">
          <h3>Average Spending by Weekday</h3>
          <img src={`data:image/png;base64,${statementData.weekday_spending}`} alt="Average Spending by Weekday" />
        </div>
        {/* <div className="insight-card">
          <h3>Average Spending by Hour</h3>
          <img src={`data:image/png;base64,${statementData.hourly_spending}`} alt="Average Spending by Hour" />
        </div> */}
        <div className="insight-card">
          <h3>Top 5 Expense Categories</h3>
          <ul>
            {statementData.top_expense_categories.map((category, index) => (
              <li key={index}>{category.name}: €{formatNumberWithSpaces(category.amount)}</li>
            ))}
          </ul>
        </div>
      </div>
    );
  };

  return (
    <div className="insights-container">
      <h1>Transaction Insights</h1>
      <div className="file-upload">
        <input type="file" onChange={handleFileUpload} accept=".csv" />
      </div>
      <div className="insights-content">
        {renderDashboard()}
        {renderInsights()}
      </div>
      {statementData && (
        <button className="categorize-button" onClick={onCategorize}>
          Categorize Transactions
        </button>
      )}
    </div>
  );
}

export default InsightsPage;