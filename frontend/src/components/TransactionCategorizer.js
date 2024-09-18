import React, { useState, useEffect } from 'react';
import axios from 'axios';

function TransactionCategorizer({ onBack, statementData, setStatementData }) {
  const [partners, setPartners] = useState([]);
  const [currentPartnerIndex, setCurrentPartnerIndex] = useState(0);
  const [categories, setCategories] = useState({});
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getNextPartners();
    getCategories();
  }, []);

  const getNextPartners = async () => {
    try {
      const response = await axios.get('http://localhost:5000/get_next_partners');
      setPartners(response.data);
      setCurrentPartnerIndex(0);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching next partners:', error);
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
      const partner = partners[currentPartnerIndex];
      await axios.post('http://localhost:5000/categorize', {
        partner: partner.partner,
        category: category,
        subcategory: subcategory || category,
        is_expense: partner.is_expense
      });
      setSelectedCategory(null);
      
      if (currentPartnerIndex < partners.length - 1) {
        setCurrentPartnerIndex(currentPartnerIndex + 1);
      } else {
        setLoading(true);
        getNextPartners();
      }
  
      // Save mapping table after each categorization
      await axios.post('http://localhost:5000/save_mapping');
    } catch (error) {
      console.error('Error categorizing partner:', error);
    }
  };

  if (loading) {
    return <div>Loading...</div>;
  }

  if (partners.length === 0) {
    return <div>No more partners to categorize.</div>;
  }

  const partner = partners[currentPartnerIndex];

  return (
    <div className="transaction-categorizer">
      <h1>Transaction Categorizer</h1>
      <div className="progress">Progress: {partner.progress}</div>
      <div className="partner-info">
        <h2>Partner: {partner.partner}</h2>
        <p>Transaction Count: {partner.transaction_count}</p>
        <p>Type: {partner.is_expense ? 'Expense' : 'Income'}</p>
        <p>Most Popular Info: {partner.most_popular_info}</p>
        <img src={`data:image/png;base64,${partner.price_distribution}`} alt="Price Distribution" />
      </div>
      <div className="categories">
        <h3>Select a category:</h3>
        {selectedCategory ? (
          <div className="subcategories">
            <h4>{categories[selectedCategory].emoji} {selectedCategory}</h4>
            <div className="grid">
              {categories[selectedCategory].subcategories.map((subcategory) => (
                <button key={subcategory.name} onClick={() => handleCategorize(selectedCategory, subcategory.name)} className="category-button">
                  {/* <span className="emoji">{subcategory.emoji}</span> */}
                  {/* <span className="category-name">{subcategory.name}</span> */}
                  <span className="category-name">{subcategory}</span>
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
      <button className="back-button" onClick={onBack}>Back to Insights</button>
    </div>
  );
}

export default TransactionCategorizer;