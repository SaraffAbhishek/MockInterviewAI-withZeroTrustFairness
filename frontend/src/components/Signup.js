import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import DOMPurify from 'dompurify';
import './Signup.css';

function Signup() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [errors, setErrors] = useState({});
  const [totpSetupData, setTotpSetupData] = useState(null);
  const [totpCode, setTotpCode] = useState('');
  const [totpVerified, setTotpVerified] = useState(false);
  const navigate = useNavigate();
  
  // Regex patterns
  const nameRegex = /^[a-zA-Z\s]{2,50}$/;
  const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
  const passwordRegex = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$/;
  
  // Input sanitization
  const sanitizeInput = (input) => {
    if (!input) return '';
    return DOMPurify.sanitize(input.trim());
  };
  
  // Validate form inputs
  const validateInputs = () => {
    const newErrors = {};
    
    const sanitizedName = sanitizeInput(name);
    if (!nameRegex.test(sanitizedName)) {
      newErrors.name = 'Name must contain only letters and spaces (2-50 characters)';
    }
    
    const sanitizedEmail = sanitizeInput(email);
    if (!emailRegex.test(sanitizedEmail)) {
      newErrors.email = 'Please enter a valid email address';
    }
    
    if (!passwordRegex.test(password)) {
      newErrors.password = 'Password must be at least 8 characters and include uppercase, lowercase, number, and special character';
    }
    
    if (password !== confirmPassword) {
      newErrors.confirmPassword = 'Passwords do not match';
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
      const sanitizedName = sanitizeInput(name);
      const sanitizedEmail = sanitizeInput(email);
      
      const response = await fetch('http://127.0.0.1:5000/api/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          name: sanitizedName, 
          email: sanitizedEmail, 
          password: password // Passwords should not be sanitized as they may contain special characters
        })
      });
      
      const data = await response.json();
      
      if(response.ok) {
        // Display TOTP setup screen
        setTotpSetupData({
          secret: data.totp_secret,
          qrCode: data.qr_code
        });
      } else {
        alert('Registration failed: ' + sanitizeInput(data.error));
      }
    } catch (error) {
      console.error('Error during registration', error);
      alert('An error occurred during registration');
    }
  };
  
  const handleTotpVerify = async (e) => {
    e.preventDefault();
    
    if (!totpCode || totpCode.length !== 6) {
      setErrors({ totpCode: 'Please enter a valid 6-digit code' });
      return;
    }
    
    try {
      const sanitizedEmail = sanitizeInput(email);
      
      const response = await fetch('http://127.0.0.1:5000/api/verify-totp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          email: sanitizedEmail, 
          totp_code: totpCode 
        })
      });
      
      const data = await response.json();
      
      if (response.ok && data.verified) {
        setTotpVerified(true);
        alert('Two-factor authentication setup successful. Please login with your credentials and authenticator code.');
        navigate('/login');
      } else {
        setErrors({ totpCode: 'Invalid authenticator code. Please try again.' });
      }
    } catch (error) {
      console.error('Error during TOTP verification', error);
      alert('An error occurred during verification');
    }
  };
  
  // Render TOTP setup screen
  if (totpSetupData) {
    return (
      <div className="signup-container">
        <h2 className="brand-name">Interview Assistant</h2>
        <h4 className="form-title">Set Up Two-Factor Authentication</h4>
        <div className="totp-setup">
          <p>Please scan this QR code with Google Authenticator app:</p>
          <img 
            src={`data:image/png;base64,${totpSetupData.qrCode}`} 
            alt="QR Code for Google Authenticator" 
            className="qr-code"
          />
          <p>Or manually enter this code in your authenticator app:</p>
          <div className="secret-key">{totpSetupData.secret}</div>
          
          <form onSubmit={handleTotpVerify} className="totp-form">
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
                required 
              />
              {errors.totpCode && <div className="invalid-feedback">{errors.totpCode}</div>}
            </div>
            <button type="submit" className="btn btn-primary">Verify & Complete Setup</button>
          </form>
        </div>
      </div>
    );
  }
  
  // Regular signup form
  return (
    <div className="signup-container">
      <h2 className="brand-name">Interview Assistant</h2>
      <h4 className="form-title">Create Account</h4>
      <form onSubmit={handleSubmit} className="signup-form">
        <div className="form-group">
          <label>Full Name</label>
          <input 
            type="text" 
            className={`form-control ${errors.name ? 'is-invalid' : ''}`}
            value={name} 
            onChange={(e) => setName(e.target.value)}
            required 
          />
          {errors.name && <div className="invalid-feedback">{errors.name}</div>}
        </div>
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
          {errors.password ? 
            <div className="invalid-feedback">{errors.password}</div> :
            <small className="form-text">Password must be at least 8 characters with uppercase, lowercase, number, and special character</small>
          }
        </div>
        <div className="form-group">
          <label>Confirm Password</label>
          <input 
            type="password" 
            className={`form-control ${errors.confirmPassword ? 'is-invalid' : ''}`}
            value={confirmPassword} 
            onChange={(e) => setConfirmPassword(e.target.value)}
            required 
          />
          {errors.confirmPassword && <div className="invalid-feedback">{errors.confirmPassword}</div>}
        </div>
        <button type="submit" className="btn btn-primary">Sign Up</button>
      </form>
      <div className="login-link">
        Already have an account? <Link to="/login">Login</Link>
      </div>
    </div>
  );
}

export default Signup;