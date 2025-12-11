import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import './ResetPasswordRequest.css';

function ResetPasswordRequest() {
  const [email, setEmail] = useState('');
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await fetch('http://127.0.0.1:5000/api/reset-password-request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email })
      });
      const data = await response.json();
      if(response.ok) {
        alert('If the email exists, a reset link has been sent.');
      } else {
        alert('Request failed: ' + data.error);
      }
    } catch (error) {
      console.error('Error during reset password request', error);
      alert('An error occurred during password reset request');
    }
  };
  
  return (
    <div className="reset-container">
      <h2 className="brand-name">Interview Assistant</h2>
      <h4 className="form-title">Reset Password</h4>
      <form onSubmit={handleSubmit} className="reset-form">
        <div className="form-group">
          <label>Email address</label>
          <input 
            type="email" 
            className="form-control" 
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required 
          />
        </div>
        <button type="submit" className="btn btn-primary">Send Reset Link</button>
      </form>
      <div className="back-link">
        <Link to="/login">Back to Login</Link>
      </div>
    </div>
  );
}

export default ResetPasswordRequest;
