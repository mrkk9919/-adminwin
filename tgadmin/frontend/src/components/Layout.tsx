import { useState, useEffect } from 'react'
import { Outlet, NavLink, useLocation } from 'react-router-dom'

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()

  // Close sidebar on route change (mobile)
  useEffect(() => {
    setSidebarOpen(false)
  }, [location])

  // Close sidebar when clicking outside on mobile
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      const sidebar = document.getElementById('sidebar')
      const toggle = document.getElementById('sidebarToggle')
      if (
        window.innerWidth < 768 &&
        sidebar?.classList.contains('show') &&
        !sidebar.contains(e.target as Node) &&
        !toggle?.contains(e.target as Node)
      ) {
        setSidebarOpen(false)
      }
    }
    document.addEventListener('click', handleClick)
    return () => document.removeEventListener('click', handleClick)
  }, [])

  return (
    <div className="d-flex">
      {/* Sidebar */}
      <nav id="sidebar" className={`sidebar ${sidebarOpen ? 'show' : ''}`}>
        <div className="sidebar-header">
          <i className="bi bi-telegram" />
          <span>TGAdmin</span>
        </div>
        <ul className="nav flex-column">
          <li className="nav-item">
            <NavLink
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
              to="/"
              end
            >
              <i className="bi bi-speedometer2" />
              <span>仪表盘</span>
            </NavLink>
          </li>
          <li className="nav-item">
            <NavLink
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
              to="/users"
            >
              <i className="bi bi-people" />
              <span>用户管理</span>
            </NavLink>
          </li>
          <li className="nav-item">
            <NavLink
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
              to="/bots"
            >
              <i className="bi bi-robot" />
              <span>机器人管理</span>
            </NavLink>
          </li>
        </ul>
      </nav>

      {/* Main content */}
      <main className="main-content">
        <header className="top-bar d-flex align-items-center justify-content-between">
          <button
            className="btn btn-link d-md-none"
            id="sidebarToggle"
            onClick={() => setSidebarOpen(!sidebarOpen)}
          >
            <i className="bi bi-list fs-4" />
          </button>
          <div className="d-flex align-items-center gap-2 ms-auto">
            <span className="badge bg-success">在线</span>
          </div>
        </header>

        <div className="content-wrapper">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
