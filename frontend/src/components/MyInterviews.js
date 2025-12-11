// MyInterviews.jsx
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';

const API_URL = 'http://localhost:5000/api';

const MyInterviews = () => {
  const [interviews, setInterviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedInterview, setExpandedInterview] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchInterviews = async () => {
      try {
        const token = localStorage.getItem('token');
        if (!token) {
          navigate('/login');
          return;
        }

        const response = await axios.get(`${API_URL}/interviews/history`, {
          headers: {
            Authorization: `Bearer ${token}`
          }
        });
        
        console.log('API Response:', response.data); // Debug to see what we're getting
        
        // Process the data to ensure scores are numbers
        const processedData = response.data.map(interview => ({
          ...interview,
          score: interview.score !== null ? parseFloat(interview.score) : null,
          questions: interview.questions.map(q => ({
            ...q,
            score: q.score !== null ? parseFloat(q.score) : null
          }))
        }));
        
        setInterviews(processedData);
        setLoading(false);
      } catch (err) {
        setError('Failed to fetch interview history. Please try again later.');
        setLoading(false);
        console.error('Error fetching interviews:', err);
      }
    };

    fetchInterviews();
  }, [navigate]);

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const toggleInterview = (interviewId) => {
    if (expandedInterview === interviewId) {
      setExpandedInterview(null);
    } else {
      setExpandedInterview(interviewId);
    }
  };

  // Calculate the average score for each question
  const calculateQuestionAverage = (questions) => {
    if (!questions || questions.length === 0) return 'N/A';
    
    const validScores = questions
      .map(q => q.score)
      .filter(score => score !== null && score !== undefined);
    
    if (validScores.length === 0) return 'N/A';
    
    const sum = validScores.reduce((acc, curr) => acc + curr, 0);
    return (sum / validScores.length).toFixed(1);
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-screen">
        <div className="text-xl font-semibold">Loading interview history...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex justify-center items-center h-screen">
        <div className="text-xl text-red-500">{error}</div>
      </div>
    );
  }

  if (interviews.length === 0) {
    return (
      <div className="container mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold mb-6">Interview History</h1>
        <div className="bg-white rounded-lg shadow-md p-6">
          <p className="text-gray-600">You haven't completed any interviews yet.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">Interview History</h1>
      
      {interviews.map((interview) => {
        // If interview score is null, calculate from questions
        const displayScore = interview.score !== null ? 
          interview.score : 
          calculateQuestionAverage(interview.questions);
          
        return (
          <div key={interview.id} className="bg-white rounded-lg shadow-md mb-6 overflow-hidden">
            <div 
              className="flex justify-between items-center p-4 cursor-pointer hover:bg-gray-50"
              onClick={() => toggleInterview(interview.id)}
            >
              <div>
                <h2 className="text-xl font-semibold">{interview.job_role}</h2>
                <p className="text-gray-600 text-sm">{formatDate(interview.created_at)}</p>
              </div>
              <div className="flex items-center">
                <div className="mr-4">
                  <span className="font-bold">Overall Score: </span>
                  <span className={`font-semibold ${getScoreColor(displayScore)}`}>
                    {displayScore !== 'N/A' ? displayScore : 'N/A'}
                  </span>
                </div>
                <svg
                  className={`w-6 h-6 transform transition-transform ${expandedInterview === interview.id ? 'rotate-180' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path>
                </svg>
              </div>
            </div>
            
            {expandedInterview === interview.id && (
              <div className="border-t border-gray-200 p-4">
                <h3 className="font-semibold mb-2">Questions & Answers</h3>
                {interview.questions.length > 0 ? (
                  <div className="space-y-4">
                    {interview.questions.map((q, index) => (
                      <div key={index} className="border-b border-gray-100 pb-3">
                        <div className="flex justify-between mb-1">
                          <p className="font-medium">{q.question}</p>
                          <span className={`px-2 py-1 rounded text-sm ${getScoreColor(q.score)}`}>
                            Score: {q.score !== null ? q.score.toFixed(1) : 'N/A'}
                          </span>
                        </div>
                        <p className="text-gray-700 text-sm">{q.answer}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-gray-600 italic">No questions found for this interview.</p>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

// Helper function to get color based on score
const getScoreColor = (score) => {
  if (score === 'N/A' || score === null) return "text-gray-500";
  
  const numScore = parseFloat(score);
  if (isNaN(numScore)) return "text-gray-500";
  
  if (numScore >= 8) return "text-green-600";
  if (numScore >= 6) return "text-yellow-600";
  return "text-red-600";
};

export default MyInterviews;