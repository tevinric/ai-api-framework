import { useState } from 'react';

export const useNavigation = () => {
  const [currentView, setCurrentView] = useState('dashboard');

  console.log('[USE_NAVIGATION] Current view:', currentView);

  const navigateTo = (view) => {
    console.log('[USE_NAVIGATION] Navigating to:', view);
    setCurrentView(view);
  };

  return {
    currentView,
    navigateTo
  };
};