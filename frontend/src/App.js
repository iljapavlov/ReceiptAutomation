import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [partner, setPartner] = useState(null);
  const [categories, setCategories] = useState({});
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getNextPartner();
    getCategories();
  }, []);

  const getNextPartner = async () => {
    try {
      const response = await axios.get('http://localhost:5000/get_next_partner');
      
      setPartner(response.data);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching next partner:', error);
      setLoading(false);
    }
  };

  const getCategories = async () => {
    try {
      const response = await axios.get('http://localhost:5000/get_categories');
      setCategories(response.data);
    } catch (error) {
      console.error('Error fetching categories:', error);
    }
  };

  const handleCategorize = async (category, subcategory = null) => {
    try {
      await axios.post('http://localhost:5000/categorize', {
        partner: partner.partner,
        category: category,
        subcategory: subcategory || category,
        is_expense: partner.is_expense
      });
      setSelectedCategory(null);
      setLoading(true);
      getNextPartner();
    } catch (error) {
      console.error('Error categorizing partner:', error);
    }
  };

  if (loading) {
    console.log('loading')
    return <div>Loading...</div>;
  }

  if (!partner) {
    return <div>No more partners to categorize.</div>;
  }

  console.log('partner loaded')
  console.log(partner);

  const formatNumber = (num) => {
    return (typeof num === 'number' && !isNaN(num)) ? num.toFixed(2) : 'N/A';
  };

  return (
    <div className="App">
      <h1>Transaction Categorizer</h1>
      <div className="progress">Progress: {partner.progress}</div>
      <div className="partner-info">
        <h2>Partner: {partner.partner}</h2>
        <p>Average Amount: {formatNumber(partner.avg_amount)}</p>
        <p>Standard Deviation: {formatNumber(partner.std_amount)}</p>
        <p>Max Amount: {formatNumber(partner.max_amount)}</p>
        <p>Min Amount: {formatNumber(partner.min_amount)}</p>
        <p>Transaction Count: {partner.transaction_count}</p>
        <p>Type: {partner.is_expense ? 'Expense' : 'Income'}</p>
        <p>Most Popular Info: {partner.most_popular_info}</p>
      </div>
      <div className="categories">
        <h3>Select a category:</h3>
        {selectedCategory ? (
          <div className="subcategories">
            <h4>{categories[selectedCategory].emoji} {selectedCategory}</h4>
            <div className="grid">
              {categories[selectedCategory].subcategories.map((subcategory) => (
                <button key={subcategory} onClick={() => handleCategorize(selectedCategory, subcategory)}>
                  {subcategory}
                </button>
              ))}
            </div>
            <button className="back-button" onClick={() => setSelectedCategory(null)}>Back to categories</button>
          </div>
        ) : (
          <div className="grid">
            {Object.entries(categories).map(([category, { emoji, subcategories }]) => (
              <button 
                key={category} 
                onClick={() => subcategories.length > 0 ? setSelectedCategory(category) : handleCategorize(category)}
                className="category-button"
              >
                <span className="emoji">{emoji}</span>
                <span className="category-name">{category}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;