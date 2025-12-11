import React, { useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import './ResetPassword.css';

function ResetPassword() {
  const [searchParams] = useSearchParams();
  const resetToken = searchParams.get('token');
  const [newPassword, setNewPassword] = useState('');
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    if(!resetToken) {
      alert('Reset token is missing');
      return;
    }
    try {
      const response = await fetch('http://127.0.0.1:5000/api/reset-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reset_token: resetToken, new_password: newPassword })
      });
      const data = await response.json();
      if(response.ok) {
        alert('Password updated successfully. Please login.');
      } else {
        alert('Password reset failed: ' + data.error);
      }
    } catch (error) {
      console.error('Error during password reset', error);
      alert('An error occurred during password reset');
    }
  };
  
  return (
    <div className="reset-container">
      <h2 className="brand-name">Interview Assistant</h2>
      <h4 className="form-title">Set New Password</h4>
      <form onSubmit={handleSubmit} className="reset-form">
        <div className="form-group">
          <label>New Password</label>
          <input 
            type="password" 
            className="form-control" 
            value={newPassword} 
            onChange={(e) => setNewPassword(e.target.value)}
            required 
          />
        </div>
        <button type="submit" className="btn btn-primary">Reset Password</button>
      </form>
      <div className="back-link">
        <Link to="/login">Back to Login</Link>
      </div>
    </div>
  );
}

export default ResetPassword;
