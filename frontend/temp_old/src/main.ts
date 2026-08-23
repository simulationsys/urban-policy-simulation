import './style.css';
import { DashboardApp } from './components/dashboard';

// Initialize the Premium Simulation Dashboard App on load
window.addEventListener('DOMContentLoaded', () => {
  try {
    (window as any).app = new DashboardApp();
  } catch (error) {
    console.error("Failed to initialize Pravaah Dashboard App:", error);
  }
});
