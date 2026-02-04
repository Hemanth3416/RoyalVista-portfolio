import json
import os
import re
import requests

class RoyalVistaAI:
    def __init__(self, chatbot_data_path):
        self.knowledge_base = {}
        self.chunks = []
        self.citations = []
        
        self.load_data(chatbot_data_path)

    def load_data(self, path):
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                self.knowledge_base = json.load(f)
        
        # Flatten knowledge base into searchable chunks
        comp = self.knowledge_base.get('company_profile', {})
        if comp:
            self.chunks.append(f"Company Info: {comp.get('name', 'RoyalVista Tech Solutions')} founded in {comp.get('founded_year', 2026)} by {comp.get('founder', 'A.V.Hemanth Kumar')}. Vision: {comp.get('vision', 'Premium digital solutions')}")
            self.citations.append("Source: Company Overview")

        for s in self.knowledge_base.get('service_catalog', []):
            service_info = f"Service: {s['name']}. {s['description']}."
            self.chunks.append(service_info)
            self.citations.append(f"Source: Services List - {s['name']}")

        ai_kb = self.knowledge_base.get('ai_knowledge_base', {})
        for faq in ai_kb.get('faq', []):
            self.chunks.append(f"FAQ: {faq['question']} Answer: {faq['answer']}")
            self.citations.append("Source: Frequently Asked Questions")

    def _fuzzy_match(self, query, keywords):
        query_lower = query.lower()
        for kw in keywords:
            if kw.lower() in query_lower:
                return True
        return False
    
    def get_chatbot_response(self, query):
        if not self.chunks:
            return {"reply": "I'm currently updating my knowledge base. Please contact our support team.", "citations": []}

        query_lower = query.lower()
        
        # Priority 1: Direct keyword mapping for specific services
        mapping = {
            'logo': 'Logo Design',
            'web': 'Web Design',
            'video': 'Video Editing',
            'poster': 'Posters & Ads',
            'payment': 'Financial Terms',
            'refund': 'Refund Policy'
        }
        
        for key, service_name in mapping.items():
            if key in query_lower:
                # Custom detailed responses for these can be pulled from JSON
                pass

        # Priority 2: Simple similarity based on word overlap
        query_words = set(re.findall(r'\w+', query_lower))
        best_score = 0
        best_idx = -1
        
        for i, chunk in enumerate(self.chunks):
            chunk_words = set(re.findall(r'\w+', chunk.lower()))
            overlap = len(query_words.intersection(chunk_words))
            score = overlap / len(query_words) if query_words else 0
            
            if score > best_score:
                best_score = score
                best_idx = i
        
        if best_idx != -1 and best_score > 0.2:
            reply = self.chunks[best_idx]
            # Cleaning
            if "FAQ:" in reply:
                reply = reply.split("Answer:")[1].strip()
            return {"reply": reply, "citations": [self.citations[best_idx]]}
            
        return None

    def generate_job_structure(self, raw_text):
        """Lighter job structure generation without heavy libraries"""
        title = "Job Opportunity"
        lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
        if lines: title = lines[0][:70]
        
        found_cats = []
        keywords = {"2024": "2024 Passout", "2025": "2025 Passout", "fresher": "Fresher"}
        for k, v in keywords.items():
            if k in raw_text.lower(): found_cats.append(v)

        return {
            "title": title,
            "description": f"<p>{raw_text[:500]}...</p>",
            "categories": found_cats,
            "eligible_years": ";".join(re.findall(r'20\d{2}', raw_text)) or "Not Specified",
            "summary": raw_text[:200],
            "tags": ";".join(found_cats)
        }
