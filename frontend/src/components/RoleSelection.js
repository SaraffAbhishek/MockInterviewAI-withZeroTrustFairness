import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './RoleSelection.css';

function RoleSelection() {
  const [roles, setRoles] = useState([]);
  const [selectedRole, setSelectedRole] = useState(null);
  const [selectedDifficulty, setSelectedDifficulty] = useState('mid');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const token = localStorage.getItem('token');

  useEffect(() => {
    fetchRoles();
  }, []);

  const fetchRoles = async () => {
    try {
      const response = await fetch('http://127.0.0.1:5000/api/roles', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      const data = await response.json();
      
      if (response.ok) {
        setRoles(data.roles);
      } else {
        setError('Failed to load interview roles');
      }
    } catch (err) {
      setError('Error connecting to server');
    } finally {
      setLoading(false);
    }
  };

  const handleStartInterview = async () => {
    if (!selectedRole) {
      alert('Please select an interview role');
      return;
    }

    try {
      const response = await fetch('http://127.0.0.1:5000/api/start-role-interview', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          roleId: selectedRole.id,
          difficultyLevel: selectedDifficulty
        })
      });

      const data = await response.json();

      if (response.ok) {
        // Navigate to dashboard with interview data
        navigate('/dashboard', {
          state: {
            interviewId: data.interview_id,
            questions: data.questions,
            role: data.role,
            difficulty: data.difficulty,
            isRoleBased: true
          }
        });
      } else {
        alert('Error starting interview: ' + data.error);
      }
    } catch (err) {
      alert('Error connecting to server');
    }
  };

  if (loading) {
    return (
      <div className="role-selection-container">
        <div className="loading-spinner">Loading interview roles...</div>
      </div>
    );
  }

  return (
    <div className="role-selection-container">
      <div className="role-selection-content">
        <header className="role-selection-header">
          <h1>Choose Your Interview Role</h1>
          <p>Select a role and difficulty level to begin your AI-powered mock interview</p>
        </header>

        {error && <div className="error-message">{error}</div>}

        <div className="roles-grid">
          {roles.map((role) => (
            <div
              key={role.id}
              className={`role-card ${selectedRole?.id === role.id ? 'selected' : ''}`}
              onClick={() => setSelectedRole(role)}
            >
              <div className="role-icon">{role.icon}</div>
              <h3 className="role-name">{role.name}</h3>
              <p className="role-description">{role.description}</p>
              {selectedRole?.id === role.id && (
                <div className="selected-indicator">✓ Selected</div>
              )}
            </div>
          ))}
        </div>

        {selectedRole && (
          <div className="difficulty-selection">
            <h2>Select Difficulty Level</h2>
            <div className="difficulty-buttons">
              <button
                className={`difficulty-btn ${selectedDifficulty === 'junior' ? 'active' : ''}`}
                onClick={() => setSelectedDifficulty('junior')}
              >
                <span className="difficulty-label">Junior</span>
                <span className="difficulty-desc">Entry-level questions</span>
              </button>
              <button
                className={`difficulty-btn ${selectedDifficulty === 'mid' ? 'active' : ''}`}
                onClick={() => setSelectedDifficulty('mid')}
              >
                <span className="difficulty-label">Mid-Level</span>
                <span className="difficulty-desc">Intermediate concepts</span>
              </button>
              <button
                className={`difficulty-btn ${selectedDifficulty === 'senior' ? 'active' : ''}`}
                onClick={() => setSelectedDifficulty('senior')}
              >
                <span className="difficulty-label">Senior</span>
                <span className="difficulty-desc">Advanced topics</span>
              </button>
            </div>
          </div>
        )}

        <div className="action-buttons">
          <button className="btn-secondary" onClick={() => navigate('/dashboard')}>
            Back to Dashboard
          </button>
          <button
            className="btn-primary"
            onClick={handleStartInterview}
            disabled={!selectedRole}
          >
            Start Interview →
          </button>
        </div>
      </div>
    </div>
  );
}

export default RoleSelection;
