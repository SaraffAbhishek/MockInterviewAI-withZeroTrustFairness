import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, Cell } from 'recharts';
import './InterviewResults.css';

function InterviewResults() {
  const { interviewId } = useParams();
  const navigate = useNavigate();
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('overview');
  const token = localStorage.getItem('token');

  useEffect(() => {
    fetchResults();
  }, [interviewId]);

  const fetchResults = async () => {
    try {
      const response = await fetch(`http://127.0.0.1:5000/api/interview-results/${interviewId}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      const data = await response.json();

      if (response.ok) {
        setResults(data);
      } else {
        setError(data.error || 'Failed to load results');
      }
    } catch (err) {
      setError('Error connecting to server');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="results-container">
        <div className="loading-spinner">Loading your results...</div>
      </div>
    );
  }

  if (error || !results) {
    return (
      <div className="results-container">
        <div className="error-message">{error || 'No results found'}</div>
        <button className="btn-primary" onClick={() => navigate('/dashboard')}>
          Back to Dashboard
        </button>
      </div>
    );
  }

  const { interview, questions, evaluation_metrics, improvement_plan } = results;

  // Prepare data for radar chart
  const radarData = evaluation_metrics ? [
    { subject: 'Technical', score: evaluation_metrics.average_technical, fullMark: 100 },
    { subject: 'Communication', score: evaluation_metrics.average_communication, fullMark: 100 },
    { subject: 'Confidence', score: evaluation_metrics.average_confidence, fullMark: 100 }
  ] : [];

  // Prepare data for bar chart (question-by-question)
  const barData = questions.map((q, index) => ({
    name: `Q${index + 1}`,
    score: q.scores.overall,
    technical: q.scores.technical,
    communication: q.scores.communication,
    confidence: q.scores.confidence
  }));

  // Color based on performance level
  const getPerformanceColor = (level) => {
    const colors = {
      'Excellent': '#10b981',
      'Good': '#3b82f6',
      'Satisfactory': '#f59e0b',
      'Needs Improvement': '#ef4444',
      'Poor': '#991b1b'
    };
    return colors[level] || '#6b7280';
  };

  const performanceColor = evaluation_metrics ? getPerformanceColor(evaluation_metrics.performance_level) : '#6b7280';

  return (
    <div className="results-container">
      <div className="results-content">
        {/* Header */}
        <header className="results-header">
          <div className="header-left">
            <h1>Interview Results</h1>
            <div className="interview-meta">
              <span className="meta-item">
                <strong>Role:</strong> {interview.role}
              </span>
              <span className="meta-item">
                <strong>Difficulty:</strong> {interview.difficulty}
              </span>
              <span className="meta-item">
                <strong>Date:</strong> {new Date(interview.created_at).toLocaleDateString()}
              </span>
            </div>
          </div>
          <div className="header-right">
            <div className="overall-score" style={{ borderColor: performanceColor }}>
              <div className="score-value" style={{ color: performanceColor }}>
                {Math.round(interview.score)}
              </div>
              <div className="score-label">Overall Score</div>
              {evaluation_metrics && (
                <div className="performance-badge" style={{ background: performanceColor }}>
                  {evaluation_metrics.performance_level}
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Tabs */}
        <div className="tabs">
          <button
            className={`tab ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            Overview
          </button>
          <button
            className={`tab ${activeTab === 'questions' ? 'active' : ''}`}
            onClick={() => setActiveTab('questions')}
          >
            Question Analysis
          </button>
          <button
            className={`tab ${activeTab === 'improvement' ? 'active' : ''}`}
            onClick={() => setActiveTab('improvement')}
          >
            Improvement Plan
          </button>
        </div>

        {/* Tab Content */}
        <div className="tab-content">
          {activeTab === 'overview' && evaluation_metrics && (
            <div className="overview-tab">
              <div className="charts-grid">
                {/* Radar Chart */}
                <div className="chart-card">
                  <h3>Score Breakdown</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <RadarChart data={radarData}>
                      <PolarGrid stroke="#e0e0e0" />
                      <PolarAngleAxis dataKey="subject" tick={{ fill: '#666', fontSize: 14 }} />
                      <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: '#999', fontSize: 12 }} />
                      <Radar name="Your Score" dataKey="score" stroke="#667eea" fill="#667eea" fillOpacity={0.6} />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>

                {/* Bar Chart */}
                <div className="chart-card">
                  <h3>Question-by-Question Performance</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={barData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                      <XAxis dataKey="name" tick={{ fill: '#666', fontSize: 12 }} />
                      <YAxis domain={[0, 100]} tick={{ fill: '#666', fontSize: 12 }} />
                      <Tooltip 
                        contentStyle={{ background: 'white', border: '1px solid #e0e0e0', borderRadius: '8px' }}
                      />
                      <Legend />
                      <Bar dataKey="score" fill="#667eea" name="Overall" radius={[8, 8, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Metrics Cards */}
              <div className="metrics-grid">
                <div className="metric-card">
                  <div className="metric-icon">🎯</div>
                  <div className="metric-value">{evaluation_metrics.average_technical.toFixed(1)}</div>
                  <div className="metric-label">Technical Score</div>
                </div>
                <div className="metric-card">
                  <div className="metric-icon">💬</div>
                  <div className="metric-value">{evaluation_metrics.average_communication.toFixed(1)}</div>
                  <div className="metric-label">Communication</div>
                </div>
                <div className="metric-card">
                  <div className="metric-icon">⚡</div>
                  <div className="metric-value">{evaluation_metrics.average_confidence.toFixed(1)}</div>
                  <div className="metric-label">Confidence</div>
                </div>
                <div className="metric-card">
                  <div className="metric-icon">📊</div>
                  <div className="metric-value">{evaluation_metrics.total_questions}</div>
                  <div className="metric-label">Questions Answered</div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'questions' && (
            <div className="questions-tab">
              {questions.map((q, index) => (
                <div key={index} className="question-card">
                  <div className="question-header">
                    <h4>Question {index + 1}</h4>
                    {q.topic && <span className="topic-badge">{q.topic}</span>}
                    <div className="question-score" style={{ 
                      background: q.scores.overall >= 70 ? '#10b981' : q.scores.overall >= 50 ? '#f59e0b' : '#ef4444'
                    }}>
                      {Math.round(q.scores.overall)}
                    </div>
                  </div>
                  <p className="question-text">{q.question}</p>
                  <div className="answer-section">
                    <strong>Your Answer:</strong>
                    <p className="answer-text">{q.answer}</p>
                  </div>
                  <div className="scores-breakdown">
                    <div className="score-item">
                      <span>Technical:</span>
                      <div className="score-bar">
                        <div className="score-fill" style={{ width: `${q.scores.technical}%`, background: '#667eea' }}></div>
                        <span className="score-text">{Math.round(q.scores.technical)}</span>
                      </div>
                    </div>
                    <div className="score-item">
                      <span>Communication:</span>
                      <div className="score-bar">
                        <div className="score-fill" style={{ width: `${q.scores.communication}%`, background: '#10b981' }}></div>
                        <span className="score-text">{Math.round(q.scores.communication)}</span>
                      </div>
                    </div>
                    <div className="score-item">
                      <span>Confidence:</span>
                      <div className="score-bar">
                        <div className="score-fill" style={{ width: `${q.scores.confidence}%`, background: '#f59e0b' }}></div>
                        <span className="score-text">{Math.round(q.scores.confidence)}</span>
                      </div>
                    </div>
                  </div>
                  {q.feedback && (
                    <div className="feedback-section">
                      <strong>Feedback:</strong>
                      <p className="feedback-text">{q.feedback}</p>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {activeTab === 'improvement' && improvement_plan && (
            <div className="improvement-tab">
              {/* Overall Recommendation */}
              <div className="recommendation-card">
                <h3>Overall Assessment</h3>
                <p className="recommendation-text">{improvement_plan.overall_recommendation}</p>
              </div>

              {/* Weak Areas */}
              {improvement_plan.weak_areas && improvement_plan.weak_areas.length > 0 && (
                <div className="section-card">
                  <h3>Areas for Improvement</h3>
                  <div className="weak-areas-grid">
                    {improvement_plan.weak_areas.map((area, index) => (
                      <div key={index} className="weak-area-card">
                        <div className="area-header">
                          <span className="area-name">{area.area}</span>
                          <span className={`severity-badge ${area.severity}`}>
                            {area.severity} priority
                          </span>
                        </div>
                        <div className="area-score">Score: {area.score.toFixed(1)}/100</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Improvement Steps */}
              {improvement_plan.improvement_steps && improvement_plan.improvement_steps.length > 0 && (
                <div className="section-card">
                  <h3>Action Plan</h3>
                  <ol className="improvement-steps">
                    {improvement_plan.improvement_steps.map((step, index) => (
                      <li key={index} className="improvement-step">{step}</li>
                    ))}
                  </ol>
                </div>
              )}

              {/* Learning Resources */}
              {improvement_plan.recommended_resources && improvement_plan.recommended_resources.length > 0 && (
                <div className="section-card">
                  <h3>Recommended Learning Resources</h3>
                  <div className="resources-grid">
                    {improvement_plan.recommended_resources.map((resource, index) => (
                      <div key={index} className="resource-card">
                        <div className="resource-type">{resource.type}</div>
                        <h4 className="resource-title">{resource.title}</h4>
                        <p className="resource-description">{resource.description}</p>
                        {resource.url && (
                          <a href={resource.url} target="_blank" rel="noopener noreferrer" className="resource-link">
                            View Resource →
                          </a>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Practice Plan */}
              {improvement_plan.practice_plan && (
                <div className="section-card">
                  <h3>Practice Plan</h3>
                  <div className="practice-plan">
                    {improvement_plan.practice_plan.split('\n').map((line, index) => (
                      <p key={index} className={line.startsWith('**') ? 'plan-heading' : 'plan-item'}>
                        {line.replace(/\*\*/g, '')}
                      </p>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div className="results-actions">
          <button className="btn-secondary" onClick={() => navigate('/dashboard')}>
            Back to Dashboard
          </button>
          <button className="btn-primary" onClick={() => navigate('/role-selection')}>
            Take Another Interview
          </button>
        </div>
      </div>
    </div>
  );
}

export default InterviewResults;
