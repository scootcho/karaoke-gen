import ReactDOM from 'react-dom/client'
import App from './App'
// Import version from package.json
import packageJson from '../package.json'

// Log the frontend version when the app loads
console.log(`🎵 Lyrics Transcriber Frontend v${packageJson.version}`)

ReactDOM.createRoot(document.getElementById('root')!).render(
  <App />
)
