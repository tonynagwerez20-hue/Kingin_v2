import React, { useEffect } from 'react';
import Sidebar from './Sidebar';
import Header from './Header';
import useStore from '../store/useStore';

const MainLayout = ({ children }) => {
  // Obtain only the syncWithEngine function from the store
  const syncWithEngine = useStore(state => state.syncWithEngine);

  useEffect(() => {
    // Start synchronization loop
    const syncInterval = setInterval(syncWithEngine, 3000);
    return () => clearInterval(syncInterval);
  }, [syncWithEngine]);

  return (
    <div className="flex h-screen bg-kg-dark text-white overflow-hidden font-inter selection:bg-kg-gold selection:text-white">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 relative">
        <Header />
        <main className="flex-1 overflow-y-auto p-8 custom-scrollbar">
          {children}
        </main>
      </div>
    </div>
  );
};

export default MainLayout;
