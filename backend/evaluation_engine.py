"""
Evaluation Engine Module
Multi-dimensional evaluation system with fairness and bias mitigation
Implements gender-neutral, accent-neutral, culturally-neutral evaluation
"""

import re
from groq import Groq
import os


class EvaluationEngine:
    def __init__(self, groq_api_key):
        self.groq_client = Groq(api_key=groq_api_key)
    
    def evaluate_response(self, question, answer, expected_points, role_criteria):
        """
        Evaluate a single interview response across multiple dimensions
        
        FAIRNESS PRINCIPLES:
        - Technical score: Pure content, grammar-blind, accent-blind
        - Communication score: Grammar matters, but accent/culture don't
        - Confidence score: Delivery matters, but cultural style doesn't
        
        Returns:
            dict with scores for communication, technical, confidence, and overall
        """
        # Get individual dimension scores
        technical_score = self._evaluate_technical_correctness(question, answer, expected_points)
        communication_score = self._evaluate_communication(answer)
        confidence_score = self._evaluate_confidence(answer)
        
        # Calculate weighted overall score based on role criteria
        weights = role_criteria
        overall_score = (
            technical_score * weights.get('technical_weight', 0.4) +
            communication_score * weights.get('communication_weight', 0.3) +
            confidence_score * weights.get('confidence_weight', 0.3)
        )
        
        # Generate detailed feedback
        feedback = self._generate_feedback(
            question, answer, expected_points,
            technical_score, communication_score, confidence_score
        )
        
        return {
            'technical_score': round(technical_score, 2),
            'communication_score': round(communication_score, 2),
            'confidence_score': round(confidence_score, 2),
            'overall_score': round(overall_score, 2),
            'feedback': feedback
        }
    
    def _evaluate_technical_correctness(self, question, answer, expected_points):
        """
        Evaluate ONLY technical accuracy and completeness
        
        FAIRNESS: This evaluation is completely grammar-blind and accent-blind.
        We only care about: Is the technical content correct?
        """
        prompt = f"""Evaluate the technical correctness of this interview answer.

CRITICAL INSTRUCTIONS FOR FAIRNESS:
1. IGNORE all grammar mistakes
2. IGNORE communication style
3. IGNORE confidence or hesitation
4. FOCUS ONLY on technical accuracy and completeness

Question: {question}

Expected Key Points:
{chr(10).join(f"- {point}" for point in expected_points)}

Candidate's Answer: {answer}

Rate the technical correctness from 0-100 based ONLY on:
1. Accuracy of technical information (40 points)
2. Coverage of expected key points (30 points)
3. Depth of technical understanding (30 points)

Even if the answer has poor grammar or sounds uncertain, if the technical content is correct, give full points.

Respond with ONLY a number between 0-100 wrapped in <SCORE></SCORE> tags.
Example: <SCORE>75</SCORE>"""

        try:
            response = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a fair technical evaluator. You evaluate ONLY technical content, completely ignoring grammar, accent, or communication style. You are gender-neutral, accent-neutral, and culturally-neutral."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.2
            )
            
            content = response.choices[0].message.content
            score_match = re.search(r'<SCORE>(.*?)</SCORE>', content, re.DOTALL)
            
            if score_match:
                score = float(re.sub(r'[^\d.]', '', score_match.group(1).strip()))
                return min(max(score, 0), 100)
            
            return 50.0  # Default if parsing fails
            
        except Exception as e:
            print(f"Error in technical evaluation: {str(e)}")
            return 50.0
    
    def _evaluate_communication(self, answer):
        """
        Evaluate grammar and clarity
        
        FAIRNESS BALANCE:
        - DO penalize: Poor grammar, unclear structure, excessive filler words
        - DON'T penalize: Accent, non-native patterns, cultural communication style
        
        Focus: Can the message be understood clearly?
        """
        words = answer.split()
        word_count = len(words)
        
        # Base score
        score = 70.0
        
        # 1. LENGTH CHECK (optimal: 50-200 words)
        if word_count < 20:
            score -= 20  # Too short, insufficient detail
        elif word_count < 50:
            score -= 10  # Somewhat short
        elif word_count > 300:
            score -= 10  # Too verbose
        
        # 2. FILLER WORDS (penalize excessive use)
        # These affect clarity regardless of accent
        filler_words = ['um', 'uh', 'like', 'you know', 'basically', 'actually', 'literally']
        filler_count = sum(answer.lower().count(filler) for filler in filler_words)
        filler_ratio = filler_count / max(word_count, 1)
        
        # Only penalize if excessive (>5% of words)
        if filler_ratio > 0.05:
            score -= min((filler_ratio - 0.05) * 200, 20)
        
        # 3. STRUCTURE (reward logical organization)
        # Universal across cultures
        structure_words = ['first', 'second', 'third', 'finally', 'however', 'therefore', 'because', 'then', 'next']
        structure_count = sum(answer.lower().count(word) for word in structure_words)
        
        if structure_count > 0:
            score += min(structure_count * 3, 15)
        
        # 4. SENTENCE STRUCTURE (basic completeness)
        sentences = [s.strip() for s in re.split(r'[.!?]+', answer) if s.strip()]
        if len(sentences) >= 2:
            score += 10  # Multiple complete thoughts
        
        # 5. GRAMMAR CHECK (via LLM - accent-neutral)
        grammar_score = self._check_grammar_clarity(answer)
        score = (score * 0.7) + (grammar_score * 0.3)  # Blend scores
        
        return min(max(score, 0), 100)
    
    def _check_grammar_clarity(self, answer):
        """
        Use LLM to check grammar while being accent-neutral
        """
        prompt = f"""Rate the grammar and clarity of this text from 0-100.

IMPORTANT FAIRNESS RULES:
1. Focus on CLARITY - can you understand the message?
2. IGNORE accent-related patterns
3. IGNORE non-native grammar if meaning is clear
4. Only penalize grammar that truly obscures meaning

Text: {answer}

Rate 0-100 where:
- 90-100: Clear and grammatically correct
- 70-89: Minor grammar issues but clear meaning
- 50-69: Some grammar issues affecting clarity
- 0-49: Significant grammar issues obscuring meaning

Return ONLY a number 0-100."""

        try:
            response = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a fair grammar evaluator. You focus on clarity of meaning, not linguistic perfection. You are accent-neutral and culturally-neutral."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=10
            )
            
            score_text = response.choices[0].message.content.strip()
            score = float(re.sub(r'[^\d.]', '', score_text))
            return min(max(score, 0), 100)
        except:
            return 70.0  # Default to passing score
    
    def _evaluate_confidence(self, answer):
        """
        Evaluate confidence and fluency
        
        FAIRNESS BALANCE:
        - DO penalize: Excessive uncertainty, incomplete answers
        - DON'T penalize: Cultural communication styles, politeness patterns
        
        Focus: Completeness and commitment to answer
        """
        # Base score
        score = 75.0
        
        # 1. UNCERTAINTY WORDS (penalize excessive hedging)
        # These indicate lack of confidence regardless of culture
        uncertainty_words = ['maybe', 'perhaps', 'i think', 'i guess', 'not sure', 'probably', 'might']
        uncertainty_count = sum(answer.lower().count(word) for word in uncertainty_words)
        
        # Penalize only if excessive (more than 2)
        if uncertainty_count > 2:
            score -= min((uncertainty_count - 2) * 8, 30)
        
        # 2. ASSERTIVE LANGUAGE (reward moderate use)
        # But don't over-reward (cultural bias)
        assertive_words = ['definitely', 'certainly', 'clearly', 'obviously', 'indeed']
        assertive_count = sum(answer.lower().count(word) for word in assertive_words)
        score += min(assertive_count * 5, 10)  # Cap at 10 points
        
        # 3. HEDGING PHRASES (penalize excessive hedging)
        hedging_phrases = ['kind of', 'sort of', 'i believe', 'in my opinion']
        hedging_count = sum(answer.lower().count(phrase) for phrase in hedging_phrases)
        
        # Some hedging is polite and acceptable
        if hedging_count > 3:
            score -= min((hedging_count - 3) * 5, 15)
        
        # 4. COMPLETENESS (reward detailed answers)
        # Detailed answers show confidence regardless of style
        word_count = len(answer.split())
        if word_count > 80:
            score += 15  # Comprehensive answer
        elif word_count > 50:
            score += 10  # Good detail
        elif word_count < 30:
            score -= 15  # Too brief, lacks confidence
        
        # 5. SPECIFICITY (reward concrete examples)
        # Universal indicator of confidence
        specific_indicators = ['for example', 'specifically', 'in my experience', 
                              'i worked on', 'i implemented', 'the result was']
        if any(indicator in answer.lower() for indicator in specific_indicators):
            score += 10
        
        return min(max(score, 0), 100)
    
    def _generate_feedback(self, question, answer, expected_points, 
                          technical_score, communication_score, confidence_score):
        """
        Generate constructive, bias-free feedback
        
        FAIRNESS: Feedback must be gender-neutral, accent-neutral, culturally-neutral
        """
        prompt = f"""Generate constructive feedback for this interview answer.

CRITICAL FAIRNESS RULES:
1. Use gender-neutral language (they/their, not he/she)
2. DO NOT mention accent, speaking style, or cultural patterns
3. Focus on content, structure, and completeness
4. Be encouraging and constructive
5. Provide actionable suggestions

Question: {question}

Expected Key Points:
{chr(10).join(f"- {point}" for point in expected_points)}

Candidate's Answer: {answer}

Scores:
- Technical: {technical_score}/100
- Communication: {communication_score}/100
- Confidence: {confidence_score}/100

Provide brief, actionable feedback in 2-3 sentences covering:
1. What was done well
2. What could be improved (focus on content, not style)
3. Specific suggestion for improvement

Keep it encouraging, fair, and bias-free."""

        try:
            response = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a fair, supportive interview coach. You provide gender-neutral, accent-neutral, culturally-neutral feedback. You focus on content and substance, not style or delivery."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=200
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"Error generating feedback: {str(e)}")
            return "Good effort on this answer. Consider providing more specific examples and structuring your response more clearly to demonstrate your knowledge."
    
    def calculate_interview_metrics(self, all_responses):
        """Calculate aggregate metrics for entire interview"""
        if not all_responses:
            return {}
        
        total_technical = sum(r['technical_score'] for r in all_responses)
        total_communication = sum(r['communication_score'] for r in all_responses)
        total_confidence = sum(r['confidence_score'] for r in all_responses)
        total_overall = sum(r['overall_score'] for r in all_responses)
        
        count = len(all_responses)
        
        return {
            'average_technical': round(total_technical / count, 2),
            'average_communication': round(total_communication / count, 2),
            'average_confidence': round(total_confidence / count, 2),
            'average_overall': round(total_overall / count, 2),
            'total_questions': count,
            'performance_level': self._get_performance_level(total_overall / count)
        }
    
    def _get_performance_level(self, score):
        """Convert score to performance level"""
        if score >= 90:
            return "Excellent"
        elif score >= 75:
            return "Good"
        elif score >= 60:
            return "Satisfactory"
        elif score >= 45:
            return "Needs Improvement"
        else:
            return "Poor"
