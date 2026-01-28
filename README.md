
# E-Numbers Lookup Application
I have it running on my server at https://enumbers.jarvisdiscordbot.net/ and there is a basic api at https://enumbers.jarvisdiscordbot.net/api/enumbers   (if you use it please don't spam it lol)

A modern web application for looking up E-number food additives with comprehensive data from Open Food Facts. Built with HTML, CSS, JavaScript, and a Python Flask API backend.

## 🌟 Features

- **Comprehensive E-Number Database**: Complete list of food additives with detailed information
- **Real-time Search**: Instant filtering by E-number code or name
- **Category Filtering**: Browse additives by functional categories
- **Data Visualization**: Interactive charts showing category distributions
- **Safety Indicators**: Visual safety level indicators for each additive
- **External Links**: Direct links to Open Food Facts and scientific research
- **Dark/Light Theme**: Toggle between themes for comfortable viewing
- **Export Functionality**: Export filtered results to CSV
- **Responsive Design**: Works perfectly on desktop and mobile devices
- **Accessibility**: Screen reader friendly with keyboard navigation
- **Auto-refresh Development**: Hot module reloading for development

## 🚀 Quick Start

### Option 1: Using Replit (Recommended)

1. **Click the Run button** in Replit to start the development server
2. **Start the Flask API** using the "Flask API Server" workflow
3. **Access the Application**: Use the provided Replit URL

### Option 2: Manual Setup

1. **Start the Flask API Server**:
   ```bash
   python start_server.py
   ```
   This starts the API server on `http://0.0.0.0:5000`

2. **Start the Development Server**:
   ```bash
   npm run dev
   ```
   This starts Vite development server with auto-refresh on `http://0.0.0.0:5173`

### Option 3: Installation Scripts

For local installation outside Replit:

**Windows:**
```cmd
install.bat
```

**Linux/macOS:**
```bash
chmod +x install-system.sh
sudo ./install-system.sh
```

## 🏗️ Project Structure

```
├── api.py                 # Flask API server with security features
├── start_server.py        # Simple server startup script
├── index.html            # Main application HTML with embedded CSS/JS
├── enumbers.json         # E-numbers database
├── install.sh            # Linux/macOS system installer
├── install.bat           # Windows installer
├── package.json          # Node.js dependencies for development
├── pyproject.toml        # Python dependencies
└── vite.config.js        # Vite development server configuration
```

## 🛡️ Security Features

The Flask API includes comprehensive security measures:

- **Content Security Policy (CSP)** - Prevents XSS attacks
- **Input Sanitization** - All user inputs are cleaned and validated
- **CORS Protection** - Configured for specific origins
- **Security Headers** - X-Frame-Options, X-Content-Type-Options, etc.
- **Rate Limiting** - Protection against DoS attacks
- **URL Validation** - Prevents malicious link injection
- **HTML Escaping** - Prevents script injection

## 📊 API Endpoints

### Public Endpoints

- `GET /` - Redirects to main application page
- `GET /enumbers.html` - E-numbers lookup page
- `GET /api/enumbers` - Get all E-numbers
- `GET /api/enumbers?q=search&limit=500` - Search E-numbers

### Admin Endpoints (requires --allow-editing flag)

- `POST /api/enumbers` - Create new E-number
- `PUT /api/enumbers/<code>` - Update E-number
- `DELETE /api/enumbers/<code>` - Delete E-number
- `POST /api/update_enumbers_from_off_additives` - Update from Open Food Facts

### Example API Usage

```bash
# Search for E-numbers containing "acid"
curl "http://0.0.0.0:5000/api/enumbers?q=acid&limit=10"

# Get specific E-number information
curl "http://0.0.0.0:5000/api/enumbers?q=E300"
```

## 🔄 Data Management

### Automatic Updates

The application automatically fetches the latest E-number data from Open Food Facts daily using a background scheduler.

### Manual Data Update

To manually trigger a data update (requires editing mode):

```bash
python api.py --allow-editing
```

Then make a POST request:
```bash
curl -X POST http://0.0.0.0:5000/api/update_enumbers_from_off_additives
```

### Data Sources

- **Open Food Facts**: Primary source for E-number information
- **Scientific Research**: Links to relevant studies and documentation

## 🎨 User Interface Features

### Search and Filtering

- **Real-time Search**: Type to filter by E-number or name
- **Category Filter**: Filter by functional categories (Colors, Preservatives, etc.)
- **Sort Options**: Sort by E-number or name
- **Clear Functions**: Easy reset of all filters

### Visualization

- **Interactive Charts**: Donut chart showing category distribution using Chart.js
- **Safety Indicators**: Color-coded safety levels (Safe, Caution, Warning, Unknown)
- **Responsive Tables**: Optimized for all screen sizes

### Accessibility

- **Keyboard Navigation**: Full keyboard support including Ctrl+K for search
- **Screen Reader Support**: ARIA labels and semantic HTML
- **Skip Links**: Direct navigation to main content
- **Reduced Motion**: Respects user's motion preferences

## 🔧 Development

### Available Workflows in Replit

- **Run Button**: Starts the Vite development server
- **Flask API Server**: Starts the Python Flask API
- **Start Flask API**: Alternative Flask startup command

### Available Scripts

- `npm run dev` - Start Vite development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `python api.py` - Start Flask API server
- `python api.py --allow-editing` - Start API with editing capabilities

### Dependencies

**Python Dependencies (pyproject.toml):**
- Flask 3.1.0 - Web framework
- Flask-CORS 5.0.0 - Cross-origin resource sharing
- APScheduler 3.11.0 - Background job scheduling
- Requests 2.32.3 - HTTP client for Open Food Facts API
- Bleach 6.2.0 - HTML sanitization
- Werkzeug 3.1.3+ - WSGI utilities

**Node.js Dependencies (package.json):**
- Vite 5.4.8 - Development server and build tool
- Chart.js 4.5.0 - Data visualization

### Adding New Features

1. **Frontend**: Modify `index.html` (contains HTML, CSS, and JavaScript)
2. **Backend**: Extend `api.py` for new endpoints
3. **Data**: Update `enumbers.json` or sync from Open Food Facts

## 🎯 Categories

The application organizes E-numbers into these categories:

- 🎨 **Colors** (E100-E199)
- 🛡️ **Preservatives** (E200-E299)
- ⚗️ **Antioxidants & Acidity Regulators** (E300-E399)
- 🥄 **Thickeners, Stabilizers & Emulsifiers** (E400-E499)
- 🧪 **Acidity Regulators & Anti-caking Agents** (E500-E599)
- 🍋 **Flavor Enhancers** (E600-E699)
- 💊 **Antibiotics** (E700-E799)
- ✨ **Glazing Agents, Sweeteners & Others** (E900-E999)
- 🧬 **Additional Chemicals** (E1000-E1999)

## 🔍 Safety Information

The application provides safety indicators based on general recognition:

- 🟢 **Safe**: Generally recognized as safe
- 🟡 **Caution**: Some concerns but generally acceptable
- 🔴 **Warning**: Potential health concerns reported
- ⚪ **Unknown**: Insufficient data available

*Note: This is for informational purposes only. Consult healthcare professionals for specific dietary advice.*

## 📄 Data Format

E-numbers are stored in JSON format:

```json
{
  "code": "E300",
  "name": "Ascorbic acid",
  "openfoodfacts_additive": {
    "name": "E300 - Ascorbic acid",
    "url": "https://world.openfoodfacts.org/facets/additives/e300-ascorbic-acid",
    "sameAs": ["https://www.wikidata.org/wiki/Q193598"]
  }
}
```

## 🚀 Deployment on Replit

This application is designed to run seamlessly on Replit:

1. Fork this repository on Replit
2. Click the **Run** button to start the development server
3. Use the **Flask API Server** workflow to start the backend
4. Your application will be available at the provided Replit URL

The application automatically handles port binding and CORS configuration for Replit's environment.

## 🤝 Contributing

1. Fork the repository on 
2. Make your changes
3. Test thoroughly using both development and API workflows
4. Submit your improvements

## 📜 License

See [LICENSE](license) file for details.

## 🔗 Links

- **Open Food Facts**: https://world.openfoodfacts.org/
- **Chart.js Documentation**: https://www.chartjs.org/
- **Flask Documentation**: https://flask.palletsprojects.com/
- **Vite Documentation**: https://vitejs.dev/

---

*Built with ❤️ for food safety awareness*
