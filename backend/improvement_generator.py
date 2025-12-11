"""
Improvement Plan Generator Module
Generates personalized improvement plans and learning resource recommendations
"""

from groq import Groq
import sqlite3
import json


class ImprovementPlanGenerator:
    def __init__(self, groq_api_key, database_path='interview_bot.db'):
        self.groq_client = Groq(api_key=groq_api_key)
        self.database_path = database_path
    
    def generate_improvement_plan(self, interview_data, evaluation_metrics, role_id):
        """
        Generate a personalized improvement plan based on interview performance
        
        Args:
            interview_data: dict with questions and answers
            evaluation_metrics: dict with scores and feedback
            role_id: integer identifying the interview role
        
        Returns:
            dict with improvement plan details
        """
        # Identify weak areas
        weak_areas = self._identify_weak_areas(evaluation_metrics)
        
        # Generate improvement steps
        improvement_steps = self._generate_improvement_steps(weak_areas, interview_data)
        
        # Recommend learning resources
        recommended_resources = self._recommend_resources(weak_areas, role_id)
        
        # Create practice plan
        practice_plan = self._create_practice_plan(weak_areas)
        
        return {
            'weak_areas': weak_areas,
            'improvement_steps': improvement_steps,
            'recommended_resources': recommended_resources,
            'practice_plan': practice_plan,
            'overall_recommendation': self._generate_overall_recommendation(evaluation_metrics)
        }
    
    def _identify_weak_areas(self, evaluation_metrics):
        """Identify areas that need improvement based on scores"""
        weak_areas = []
        
        avg_technical = evaluation_metrics.get('average_technical', 0)
        avg_communication = evaluation_metrics.get('average_communication', 0)
        avg_confidence = evaluation_metrics.get('average_confidence', 0)
        
        # Threshold for "weak" is below 70
        if avg_technical < 70:
            weak_areas.append({
                'area': 'Technical Knowledge',
                'score': avg_technical,
                'severity': 'high' if avg_technical < 50 else 'medium'
            })
        
        if avg_communication < 70:
            weak_areas.append({
                'area': 'Communication Skills',
                'score': avg_communication,
                'severity': 'high' if avg_communication < 50 else 'medium'
            })
        
        if avg_confidence < 70:
            weak_areas.append({
                'area': 'Confidence & Fluency',
                'score': avg_confidence,
                'severity': 'high' if avg_confidence < 50 else 'medium'
            })
        
        return weak_areas
    
    def _generate_improvement_steps(self, weak_areas, interview_data):
        """Generate specific, actionable improvement steps"""
        if not weak_areas:
            return ["Great job! Continue practicing to maintain your performance level."]
        
        prompt = f"""Based on these weak areas from an interview, generate 5 specific, actionable improvement steps.

Weak Areas:
{chr(10).join(f"- {area['area']}: {area['score']}/100 ({area['severity']} priority)" for area in weak_areas)}

Generate 5 concrete action items the candidate should take to improve. Each should be:
- Specific and actionable
- Achievable within 2-4 weeks
- Focused on the identified weak areas

Format as a numbered list."""

        try:
            response = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a career coach providing actionable improvement advice."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=400
            )
            
            content = response.choices[0].message.content.strip()
            # Parse numbered list
            steps = [line.strip() for line in content.split('\n') if line.strip() and any(char.isdigit() for char in line[:3])]
            return steps if steps else [content]
            
        except Exception as e:
            print(f"Error generating improvement steps: {str(e)}")
            return [
                "Review fundamental concepts in your weak areas",
                "Practice explaining technical concepts clearly",
                "Record yourself answering practice questions",
                "Seek feedback from peers or mentors",
                "Take online courses to strengthen knowledge gaps"
            ]
    
    def _recommend_resources(self, weak_areas, role_id):
        """Recommend learning resources from database based on weak areas"""
        recommendations = []
        
        try:
            with sqlite3.connect(self.database_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Get user_id from role_id
                cursor.execute('SELECT user_id FROM custom_roles WHERE id = ?', (role_id,))
                role_data = cursor.fetchone()
                
                if not role_data:
                    return []
                
                user_id = role_data['user_id']
                
                # Fetch resources from database
                cursor.execute('''
                    SELECT title, type, url, description, tags
                    FROM custom_resources
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                ''', (user_id,))
                
                all_resources = cursor.fetchall()
                
                # Match resources to weak areas based on tags
                for weak_area in weak_areas:
                    area_name = weak_area['area'].lower()
                    
                    for resource in all_resources:
                        tags = json.loads(resource['tags']) if resource['tags'] else []
                        tags_lower = [tag.lower() for tag in tags]
                        
                        # Match based on area keywords
                        if ('technical' in area_name and any(t in tags_lower for t in ['technical', 'coding', 'algorithms', 'system design'])) or \
                           ('communication' in area_name and any(t in tags_lower for t in ['communication', 'presentation', 'soft skills'])) or \
                           ('confidence' in area_name and any(t in tags_lower for t in ['confidence', 'practice', 'interview prep'])):
                            
                            recommendations.append({
                                'title': resource['title'],
                                'type': resource['type'],
                                'url': resource['url'],
                                'description': resource['description']
                            })
                            
                            # Limit to 2 resources per weak area
                            if len([r for r in recommendations if any(keyword in r['description'].lower() for keyword in area_name.split())]) >= 2:
                                break
                
        except Exception as e:
            print(f"Error fetching resources from database: {str(e)}")
        
        # If no resources found, return empty list (user needs to add their own)
        return recommendations[:6]  # Limit total recommendations
    
    def _create_practice_plan(self, weak_areas):
        """Create a structured practice plan"""
        if not weak_areas:
            return "Continue regular practice with mock interviews to maintain your skill level."
        
        plan_parts = []
        
        # Week 1-2
        plan_parts.append("**Week 1-2: Foundation Building**")
        plan_parts.append("- Study core concepts in your weak areas (1 hour daily)")
        plan_parts.append("- Watch educational videos and take notes")
        plan_parts.append("- Complete practice exercises")
        
        # Week 3-4
        plan_parts.append("\n**Week 3-4: Active Practice**")
        plan_parts.append("- Practice answering interview questions (30 min daily)")
        plan_parts.append("- Record yourself and review for improvement")
        plan_parts.append("- Participate in mock interviews with peers")
        
        # Ongoing
        plan_parts.append("\n**Ongoing:**")
        plan_parts.append("- Join study groups or online communities")
        plan_parts.append("- Read industry blogs and articles")
        plan_parts.append("- Build projects to apply your knowledge")
        
        return '\n'.join(plan_parts)
    
    def _generate_overall_recommendation(self, evaluation_metrics):
        """Generate overall recommendation based on performance"""
        avg_score = evaluation_metrics.get('average_overall', 0)
        performance_level = evaluation_metrics.get('performance_level', 'Unknown')
        
        if avg_score >= 85:
            return f"Excellent performance ({performance_level})! You're well-prepared for interviews. Focus on maintaining this level and staying updated with industry trends."
        elif avg_score >= 70:
            return f"Good performance ({performance_level})! You have a solid foundation. Work on the identified weak areas to reach the next level."
        elif avg_score >= 55:
            return f"Satisfactory performance ({performance_level}). You have potential but need focused improvement in key areas. Follow the practice plan diligently."
        else:
            return f"Your performance needs improvement ({performance_level}). Don't be discouraged! Focus on building strong fundamentals and practice consistently."
