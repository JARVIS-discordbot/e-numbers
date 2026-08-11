# Changelog

## [released]

### 🚀 Features
- **API Resilience**:  
  - Fixed API endpoint issue  
  - Added fallback to load from local JSON when Flask API isn't running  
  - Created proper workflows for both Vite dev server and Flask API  
  - App now works regardless of whether the Flask API is running, improving development and demo robustness

- **Data Export**:  
  - Added CSV export for filtered results  
  - Keyboard shortcut: `Ctrl+E` to export  

- **Keyboard Shortcuts**:  
  - `Ctrl+K` – Focus search  
  - `Escape` – Clear search  
  - `Ctrl+E` – Export CSV  
  - `Ctrl+D` – Toggle charts  
  - Arrow keys – Navigate table cells  

- **Tooltips & UX Enhancements**:  
  - Added helpful tooltips throughout the UI  
  - Improved error handling and mobile responsiveness  
  - Updated search placeholder to display relevant keyboard shortcut

- **Simple Server Startup**:  
  - Added script to start the server easily

---

### 📊 Data Visualization
- Interactive doughnut chart showing E-number distribution by category  
- Dynamic chart updates based on search filters  
- Toggle visibility with a `Ctrl+D` shortcut

---

### 📱 Mobile Responsiveness
- Improved chart layout for small screens  
- Better spacing, sizing, and touch targets for mobile users

---

### ♿ Accessibility
- Skip link for screen readers  
- ARIA labels and roles throughout  
- Keyboard navigation for table cells (arrow keys)  
- Screen reader announcements for dynamic content  
- High contrast mode support  
- Respects reduced motion preferences  
- Visible focus indicators for all interactive elements

---

### 🖨️ Print-Friendly Styles
- Clean, black-and-white print layout  
- Hides interactive elements when printing  
- Displays full URLs for links  
- Optimized font sizes and spacing  
- Adds print date header  
- Page break handling

---

### 🎨 Visual Enhancements
- **Interactive Stats Dashboard**:
  - Displays total E-numbers, categories, current results, and generally safe items
- **Safety Color Indicators**:
  - 🟢 Green: Generally safe  
  - 🟡 Yellow: Use with caution  
  - 🔴 Red: Potential concerns  
  - ⚫ Gray: Unknown/insufficient data
- **Animations**:
  - Smooth slide-in for table rows  
  - Pulsing safety indicators  
  - Loading skeleton effect  
  - Gradient shimmer  
  - Hover transformations
- **Modern Design**:
  - Glassmorphism cards with backdrop blur  
  - Gradient buttons with shine effects  
  - Floating label inputs  
  - Animated gradient headers  
  - Enhanced icons
- **Polish**:
  - Staggered row animations  
  - Smooth theme transitions with scaling effects  
  - Better typography with gradient text effects  
  - Improved button hovers and focus states

---

### 📌 Notes
For full API functionality:
1. Start the **Flask API Server** workflow first
2. Start the **Dev Server**

Keyboard shortcuts:
- `Ctrl+K` – Search  
- `Escape` – Clear search  
- `Ctrl+E` – Export CSV  
- `Ctrl+D` – Toggle charts  

---

