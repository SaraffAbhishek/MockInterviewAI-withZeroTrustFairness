import React from 'react';
import { NavLink } from 'react-router-dom';
import './Sidebar.css';

function Sidebar({ onLogout }) {
  return (
    <div className="sidebar">
      <div className="sidebar-heading">
        Interview Assistant
      </div>
      <hr className="sidebar-divider" />
      <nav className="nav">
        <NavLink to="/dashboard" className="nav-link" activeclassname="active">
          <i className="fas fa-tachometer-alt"></i> Dashboard
        </NavLink>
        <NavLink to="/my-interviews" className="nav-link" activeclassname="active">
          <i className="fas fa-list"></i> My Interviews
        </NavLink>
        <NavLink to="/dashboard" className="nav-link" activeclassname="active">
          <i className="fas fa-cog"></i> Settings
        </NavLink>
      </nav>
      <hr className="sidebar-divider" />
      <div className="nav-item">
        <button className="nav-link logout-button" onClick={onLogout}>
          <i className="fas fa-sign-out-alt"></i> Logout
        </button>
      </div>
    </div>
  );
}

export default Sidebar;
