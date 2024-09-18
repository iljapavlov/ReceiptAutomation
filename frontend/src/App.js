import React, { useState } from 'react';
import './App.css';
import TransactionCategorizer from './components/TransactionCategorizer';
import InsightsPage from './components/InsightsPage';

function App() {
  const [currentPage, setCurrentPage] = useState('insights');
  const [statementData, setStatementData] = useState(null);

  return (
    <div className="App">
      {currentPage === 'insights' ? (
        <InsightsPage 
          onCategorize={() => setCurrentPage('categorizer')}
          statementData={statementData}
          setStatementData={setStatementData}
        />
      ) : (
        <TransactionCategorizer 
          onBack={() => setCurrentPage('insights')}
          statementData={statementData}
          setStatementData={setStatementData}
        />
      )}
    </div>
  );
}

export default App;