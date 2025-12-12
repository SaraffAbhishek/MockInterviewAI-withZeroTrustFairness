import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import DOMPurify from 'dompurify';
import './Login.css';

function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [totpCode, setTotpCode] = useState('');
  const [errors, setErrors] = useState({});
  const [showTotpInput, setShowTotpInput] = useState(false);
  const navigate = useNavigate();
  
  // Regex patterns
  const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
  
  // Input sanitization
  const sanitizeInput = (input) => {
    if (!input) return '';
    return DOMPurify.sanitize(input.trim());
  };
  
  // Validate form inputs
  const validateInputs = () => {
    const newErrors = {};
    
    const sanitizedEmail = sanitizeInput(email);
    if (!emailRegex.test(sanitizedEmail)) {
      newErrors.email = 'Please enter a valid email address';
    }
    
    // We're not validating password format here as it's a login form
    // and we want to allow whatever format the user initially registered with
    if (!password) {
      newErrors.password = 'Password is required';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };
  
  // Validate TOTP code
  const validateTotpCode = () => {
    const newErrors = {};
    
    if (!totpCode || totpCode.length !== 6 || !/^\d+$/.test(totpCode)) {
      newErrors.totpCode = 'Please enter a valid 6-digit code';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validateInputs()) {
      return;
    }
    
    try {
      const sanitizedEmail = sanitizeInput(email);
      
      const response = await fetch('http://127.0.0.1:5000/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          email: sanitizedEmail, 
          password: password, // Passwords should not be sanitized as they may contain special characters
          totp_code: totpCode || undefined // Only send if provided
        })
      });
      
      const data = await response.json();
      
      if (response.ok) {
        if (data.require_totp) {
          // Show TOTP input if required
          setShowTotpInput(true);
          return;
        }
        
        // Check if we have the required data
        if (!data.access_token || !data.user) {
          console.error('Missing token or user data in response:', data);
          alert('Login failed: Invalid response from server');
          return;
        }
        
        // Store sanitized user data
        const sanitizedUser = Object.fromEntries(
          Object.entries(data.user).map(([key, value]) => 
            [key, typeof value === 'string' ? sanitizeInput(value) : value]
          )
        );
        
        localStorage.setItem('token', sanitizeInput(data.access_token));
        localStorage.setItem('refresh_token', sanitizeInput(data.refresh_token));
        localStorage.setItem('user', JSON.stringify(sanitizedUser));
        
        // Navigate to dashboard
        navigate('/dashboard');
        
        // Reload the page after successful login and navigation
        window.location.reload();
      } else {
        alert('Login failed: ' + sanitizeInput(data.error));
      }
    } catch (error) {
      console.error('Error during login', error);
      alert('An error occurred during login');
    }
  };
  
  const handleTotpSubmit = async (e) => {
    e.preventDefault();
    
    if (!validateTotpCode()) {
      return;
    }
    
    try {
      const sanitizedEmail = sanitizeInput(email);
      
      const response = await fetch('http://127.0.0.1:5000/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          email: sanitizedEmail, 
          password: password,
          totp_code: totpCode
        })
      });
      
      const data = await response.json();
      
      if (response.ok && !data.require_totp) {
        // Check if we have the required data
        if (!data.access_token || !data.user) {
          console.error('Missing token or user data in response:', data);
          setErrors({ totpCode: 'Invalid response from server' });
          return;
        }
        
        // Store sanitized user data
        const sanitizedUser = Object.fromEntries(
          Object.entries(data.user).map(([key, value]) => 
            [key, typeof value === 'string' ? sanitizeInput(value) : value]
          )
        );
        
        localStorage.setItem('token', sanitizeInput(data.access_token));
        localStorage.setItem('refresh_token', sanitizeInput(data.refresh_token));
        localStorage.setItem('user', JSON.stringify(sanitizedUser));
        
        // Navigate to dashboard
        navigate('/dashboard');
        
        // Reload the page after successful login and navigation
        window.location.reload();
      } else {
        setErrors({ totpCode: 'Invalid authenticator code' });
      }
    } catch (error) {
      console.error('Error during TOTP verification', error);
      alert('An error occurred during login');
    }
  };
  
  // Show TOTP input form if required
  if (showTotpInput) {
    return (
      <div className="login-container">
        <h2 className="brand-name">Interview Assistant</h2>
        <h4 className="form-title">Two-Factor Authentication</h4>
        <form onSubmit={handleTotpSubmit} className="login-form">
          <div className="form-group">
            <label>Enter the 6-digit code from your authenticator app</label>
            <input 
              type="text" 
              className={`form-control ${errors.totpCode ? 'is-invalid' : ''}`}
              value={totpCode} 
              onChange={(e) => setTotpCode(e.target.value.replace(/[^0-9]/g, '').slice(0, 6))}
              placeholder="000000"
              pattern="[0-9]{6}"
              maxLength="6"
              autoFocus
              required 
            />
            {errors.totpCode && <div className="invalid-feedback">{errors.totpCode}</div>}
          </div>
          <button type="submit" className="btn btn-primary">Verify & Login</button>
          <button 
            type="button" 
            className="btn btn-link" 
            onClick={() => setShowTotpInput(false)}
          >
            Back to login
          </button>
        </form>
      </div>
    );
  }
  
  // Regular login form
  return (
    <div className="login-container">
      <h2 className="brand-name">Interview Assistant</h2>
      <form onSubmit={handleSubmit} className="login-form">
        <div className="form-group">
          <label>Email address</label>
          <input 
            type="email" 
            className={`form-control ${errors.email ? 'is-invalid' : ''}`}
            value={email} 
            onChange={(e) => setEmail(e.target.value)}
            required 
          />
          {errors.email && <div className="invalid-feedback">{errors.email}</div>}
        </div>
        <div className="form-group">
          <label>Password</label>
          <input 
            type="password" 
            className={`form-control ${errors.password ? 'is-invalid' : ''}`}
            value={password} 
            onChange={(e) => setPassword(e.target.value)}
            required 
          />
          {errors.password && <div className="invalid-feedback">{errors.password}</div>}
        </div>
        <div className="forgot-password">
          <Link to="/reset-password-request">Forgot Password?</Link>
        </div>
        <button type="submit" className="btn btn-primary">Login</button>
      </form>
      <div className="signup-link">
        Don't have an account? <Link to="/signup">Sign Up</Link>
      </div>
    </div>
  );
}

export default Login;