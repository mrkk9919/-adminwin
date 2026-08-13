import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
// eslint-disable-next-line @typescript-eslint/no-explicit-any
import * as bootstrap from 'bootstrap/dist/js/bootstrap.bundle.min.js' // no bundled type declarations
import App from './App'

import 'bootstrap/dist/css/bootstrap.min.css'
import 'bootstrap-icons/font/bootstrap-icons.css'
import './styles.css'

const ROUTER_BASENAME = (import.meta.env.BASE_URL || '/').replace(/\/$/, '') || '/'

// Bootstrap's JS is imported as an ES module here (rather than a plain
// <script> tag), so it doesn't attach itself to `window` automatically.
// Modal components (BanModal, BotFormModal, ...) rely on `window.bootstrap`.
;(window as unknown as { bootstrap: typeof bootstrap }).bootstrap = bootstrap

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter basename={ROUTER_BASENAME}>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
)
