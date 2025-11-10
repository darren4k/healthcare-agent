# Agentic SOAP Portal - Web Frontend

React-based web portal for submitting and managing clinical notes.

## 🚀 Quick Start

### Prerequisites
- Node.js 18+ and npm
- Backend API running at `http://localhost:8001`

### Installation

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Open browser to http://localhost:3000
```

### Build for Production

```bash
# Build optimized bundle
npm run build

# Preview production build
npm run preview
```

## 📁 Project Structure

```
frontend/
├── src/
│   ├── api/
│   │   └── client.js          # API client with axios
│   ├── pages/
│   │   ├── SubmitPage.jsx     # Note submission form
│   │   ├── DashboardPage.jsx  # Tasks dashboard
│   │   └── TaskDetailPage.jsx # SOAP note viewer
│   ├── App.jsx                # Main app with routing
│   ├── main.jsx               # Entry point
│   └── index.css              # Tailwind styles
├── package.json
├── vite.config.js
└── tailwind.config.js
```

## 🎨 Features

### Submit Note Page (`/`)
- **Patient Information**: ID, name, DOB
- **Visit Details**: Date, time, type (PT/OT/SLP/etc.)
- **Clinical Notes**: Raw text input
- **Validation**: Required fields, minimum length
- **Real-time Feedback**: Success/error messages
- **Navigation**: Auto-redirect to task detail after submission

### Dashboard (`/dashboard`)
- **Overview Stats**: Total, processing, completed, failed
- **Search**: Filter by patient ID
- **Table View**: All submitted notes with status
- **Quick Actions**: View details for each note

### Task Detail (`/tasks/:id`)
- **Status Display**: Current processing status
- **SOAP Components**: Structured display of S/O/A/P
- **Confidence Score**: AI confidence visualization
- **Auto-refresh**: Polls for updates while processing
- **Actions**: Send to EMR, edit, copy (future)

## 🛠️ Technology Stack

- **React 18**: UI library
- **Vite**: Build tool and dev server
- **React Router**: Client-side routing
- **TailwindCSS**: Utility-first styling
- **React Hook Form**: Form validation
- **TanStack Query**: Data fetching and caching
- **Axios**: HTTP client
- **date-fns**: Date formatting
- **lucide-react**: Icon library

## 🔧 Configuration

### Environment Variables

Create `.env` file:

```bash
VITE_API_URL=http://localhost:8001
```

### API Proxy

Vite development server proxies `/api` requests to backend:

```javascript
// vite.config.js
server: {
  proxy: {
    '/api': 'http://localhost:8001'
  }
}
```

## 🎨 Styling

### TailwindCSS Classes

Custom utility classes defined in `index.css`:

- `.btn`, `.btn-primary`, `.btn-secondary` - Button styles
- `.input` - Form input styling
- `.label` - Form label styling
- `.card` - Card container
- `.badge-*` - Status badges

### Color Scheme

Primary: Blue (`primary-*`)
Success: Green
Warning: Yellow
Error: Red

## 📱 Responsive Design

- **Mobile-first**: Optimized for touch interfaces
- **Breakpoints**: `sm`, `md`, `lg`, `xl`, `2xl`
- **Grid Layouts**: Responsive columns
- **Navigation**: Mobile-friendly menu

## 🧪 Development

### Hot Reload

Changes automatically refresh in browser:

```bash
npm run dev
```

### Linting

```bash
npm run lint
```

### Building

```bash
# Development build
npm run build

# Production build with optimizations
NODE_ENV=production npm run build
```

## 🔐 Security

- **Input Validation**: Client-side validation with react-hook-form
- **CORS**: Handled by backend API
- **HTTPS**: Use in production
- **PHI Protection**: No local storage of patient data

## 🚀 Deployment

### Static Hosting (Vercel, Netlify)

```bash
# Build
npm run build

# Deploy dist/ folder
```

### Docker

```bash
# Build image
docker build -t soap-portal .

# Run container
docker run -p 3000:80 soap-portal
```

### Nginx

```nginx
server {
    listen 80;
    root /var/www/soap-portal;
    index index.html;

    location / {
        try_files $uri /index.html;
    }

    location /api {
        proxy_pass http://localhost:8001;
    }
}
```

## 🐛 Troubleshooting

### API Connection Error

**Problem**: "Network Error" or "Failed to fetch"

**Solution**:
1. Check backend is running: `curl http://localhost:8001/health`
2. Verify VITE_API_URL in `.env`
3. Check browser console for CORS errors

### Build Errors

**Problem**: "Module not found"

**Solution**:
```bash
rm -rf node_modules package-lock.json
npm install
```

### Slow Development Server

**Problem**: Hot reload takes too long

**Solution**:
```bash
# Clear Vite cache
rm -rf node_modules/.vite
npm run dev
```

## 📝 Future Enhancements

- [ ] Patient autocomplete/search
- [ ] Voice input for clinical notes
- [ ] Offline support (PWA)
- [ ] Dark mode
- [ ] Multi-language support
- [ ] Advanced filtering and sorting
- [ ] Export SOAP notes (PDF, Word)
- [ ] Clinician feedback interface
- [ ] Real-time notifications (WebSocket)

## 📞 Support

For issues:
1. Check browser console for errors
2. Verify backend API is running
3. Review network tab in DevTools
4. Check this README for common issues

---

**Built with React + Vite + TailwindCSS**
