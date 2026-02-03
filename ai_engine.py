import json
import os
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import requests

class RoyalVistaAI:
    def __init__(self, chatbot_data_path):
        self.knowledge_base = {}
        self.chunks = []
        self.citations = []
        self.vectorizer = TfidfVectorizer(stop_words='english')
        self.tfidf_matrix = None
        
        self.load_data(chatbot_data_path)
        self.index_data()

    def load_data(self, path):
        if os.path.exists(path):
            with open(path, 'r') as f:
                self.knowledge_base = json.load(f)
        
        # Flatten knowledge base into searchable chunks
        # 1. Company Profile
        comp = self.knowledge_base.get('company_profile', {})
        if comp:
            self.chunks.append(f"Company Info: {comp.get('name', 'RoyalVista Tech Solutions')} was founded in {comp.get('founded_year', 2026)} by {comp.get('founder', 'A.V.Hemanth Kumar')}. Vision: {comp.get('vision', 'Premium digital solutions')}")
            self.citations.append("Source: Company Overview")
            
            # Tagline
            if comp.get('tagline'):
                self.chunks.append(f"Company Tagline: {comp.get('tagline')}")
                self.citations.append("Source: Company Branding")

        # 2. Service Catalog
        for s in self.knowledge_base.get('service_catalog', []):
            service_info = f"Service: {s['name']}. Description: {s['description']}."
            if 'features' in s:
                service_info += f" Features: {', '.join(s['features'])}."
            if 'deliverables' in s:
                service_info += f" Deliverables: {', '.join(s['deliverables'])}."
            if 'specialties' in s:
                service_info += f" Specialties: {', '.join(s['specialties'])}."
            if 'use_cases' in s:
                service_info += f" Use Cases: {', '.join(s['use_cases'])}."
            
            self.chunks.append(service_info)
            self.citations.append(f"Source: Services List - {s['name']}")

        # 3. Financial Terms & Policies
        financial = self.knowledge_base.get('financial_terms', {})
        if financial:
            # Payment Structure
            payment = financial.get('payment_structure', {})
            if payment:
                self.chunks.append(f"Payment Policy: {payment.get('mandatory_advance', '50% advance required')}. {payment.get('final_payment', 'Balance due upon completion')}")
                self.citations.append("Source: Payment Terms")
            
            # Refund Policy
            refund = financial.get('refund_policy', {})
            if refund:
                refund_info = f"Refund Policy: Pre-confirmation: {refund.get('pre_confirmation', 'N/A')}. Post-confirmation: {refund.get('post_confirmation', 'No refunds')}."
                self.chunks.append(refund_info)
                self.citations.append("Source: Refund Policy")

        # 4. Operational Workflow
        workflow = self.knowledge_base.get('operational_workflow', {})
        if workflow:
            if workflow.get('onboarding'):
                self.chunks.append(f"Project Onboarding Process: {workflow.get('onboarding')}")
                self.citations.append("Source: Workflow & Process")
            
            # Production stages
            stages = workflow.get('production_stages', [])
            if stages:
                stage_desc = "Project Production Stages: " + "; ".join([f"Step {s['step']}: {s['name']} - {s['desc']}" for s in stages])
                self.chunks.append(stage_desc)
                self.citations.append("Source: Production Process")

        # 5. FAQs from AI Knowledge Base
        ai_kb = self.knowledge_base.get('ai_knowledge_base', {})
        for faq in ai_kb.get('faq', []):
            self.chunks.append(f"FAQ: {faq['question']} Answer: {faq['answer']}")
            self.citations.append("Source: Frequently Asked Questions")
        
        # Target Audience
        if ai_kb.get('target_audience'):
            audience_info = "Our Target Clients: " + ", ".join(ai_kb.get('target_audience', []))
            self.chunks.append(audience_info)
            self.citations.append("Source: Business Profile")

    def index_data(self):
        if self.chunks:
            self.tfidf_matrix = self.vectorizer.fit_transform(self.chunks)

    def _fuzzy_match(self, query, keywords):
        """Check if any keyword or partial keyword matches the query"""
        query_words = query.lower().split()
        for keyword in keywords:
            keyword_lower = keyword.lower()
            # Exact match
            if keyword_lower in query:
                return True
            # Partial word match (at least 4 chars)
            for word in query_words:
                if len(word) >= 4 and word in keyword_lower:
                    return True
                if len(keyword_lower) >= 4 and keyword_lower in word:
                    return True
            # Check individual words in multi-word keywords
            keyword_words = keyword_lower.split()
            for kw in keyword_words:
                if len(kw) >= 4:
                    for qw in query_words:
                        if len(qw) >= 4 and (kw in qw or qw in kw):
                            return True
        return False
    
    def get_chatbot_response(self, query):
        if not self.chunks:
            return {"reply": "I'm currently updating my knowledge base. Please contact our support team.", "citations": []}

        query_lower = query.lower()
        
        # Keyword-based matching for common queries with fuzzy matching
        # Company Profile queries
        company_keywords = ['company', 'profile', 'about', 'who', 'royalvista', 'info', 'founded', 'founder', 'vision']
        if self._fuzzy_match(query_lower, company_keywords) and not self._fuzzy_match(query_lower, ['service', 'logo', 'web', 'video']):
            comp = self.knowledge_base.get('company_profile', {})
            reply = f"<strong>{comp.get('name', 'RoyalVista Tech Solutions')}</strong> was founded in {comp.get('founded_year', 2026)} by {comp.get('founder', 'A.V.Hemanth Kumar')}. "
            reply += f"<br><br><strong>Vision:</strong> {comp.get('vision', 'To provide premium digital solutions with unmatched quality and speed.')}"
            reply += f"<br><br><strong>Tagline:</strong> {comp.get('tagline', 'Premium Quality. Unmatched Speed.')}"
            return {"reply": reply, "citations": ["Source: Company Overview"]}
        
        # Logo Design queries
        logo_keywords = ['logo', 'brand', 'identity', 'branding', 'design logo']
        if self._fuzzy_match(query_lower, logo_keywords):
            for s in self.knowledge_base.get('service_catalog', []):
                if s.get('name', '').lower() == 'logo design':
                    reply = f"<strong>Logo Design Service</strong><br><br>{s.get('description', '')}"
                    if 'deliverables' in s:
                        reply += f"<br><br><strong>Deliverables:</strong><br>• " + "<br>• ".join(s['deliverables'])
                    return {"reply": reply, "citations": ["Source: Services - Logo Design"]}
        
        # Web Design queries
        web_keywords = ['web', 'website', 'site', 'development', 'webpage']
        if self._fuzzy_match(query_lower, web_keywords) and self._fuzzy_match(query_lower, ['design', 'develop', 'create', 'build']):
            for s in self.knowledge_base.get('service_catalog', []):
                if s.get('name', '').lower() == 'web design':
                    reply = f"<strong>Web Design Service</strong><br><br>{s.get('description', '')}"
                    if 'features' in s:
                        reply += f"<br><br><strong>Features:</strong><br>• " + "<br>• ".join(s['features'])
                    return {"reply": reply, "citations": ["Source: Services - Web Design"]}
        
        # Video Editing queries
        video_keywords = ['video', 'editing', 'edit', 'footage', 'clip', 'vdo']
        if self._fuzzy_match(query_lower, video_keywords):
            for s in self.knowledge_base.get('service_catalog', []):
                if s.get('name', '').lower() == 'video editing':
                    reply = f"<strong>Video Editing Service</strong><br><br>{s.get('description', '')}"
                    if 'specialties' in s:
                        reply += f"<br><br><strong>Specialties:</strong><br>• " + "<br>• ".join(s['specialties'])
                    return {"reply": reply, "citations": ["Source: Services - Video Editing"]}
        
        # Poster/Thumbnail queries
        poster_keywords = ['poster', 'thumbnail', 'thumb', 'social media', 'graphic']
        if self._fuzzy_match(query_lower, poster_keywords):
            for s in self.knowledge_base.get('service_catalog', []):
                if 'poster' in s.get('name', '').lower() or 'thumbnail' in s.get('name', '').lower():
                    reply = f"<strong>{s.get('name', '')}</strong><br><br>{s.get('description', '')}"
                    if 'use_cases' in s:
                        reply += f"<br><br><strong>Use Cases:</strong><br>• " + "<br>• ".join(s['use_cases'])
                    return {"reply": reply, "citations": [f"Source: Services - {s.get('name', '')}"]}
        
        # Services general query
        service_keywords = ['service', 'offer', 'provide', 'what do you', 'what can']
        if self._fuzzy_match(query_lower, service_keywords):
            services = self.knowledge_base.get('service_catalog', [])
            reply = "<strong>Our Services:</strong><br><br>"
            for s in services:
                reply += f"• <strong>{s.get('name', '')}</strong>: {s.get('description', '')}<br>"
            return {"reply": reply, "citations": ["Source: Service Catalog"]}
        
        # Payment/Pricing queries
        payment_keywords = ['payment', 'pay', 'price', 'pricing', 'cost', 'charge', 'fee', 'advance', 'deposit', 'money', 'much']
        if self._fuzzy_match(query_lower, payment_keywords) and not self._fuzzy_match(query_lower, ['refund', 'cancel']):
            financial = self.knowledge_base.get('financial_terms', {})
            payment = financial.get('payment_structure', {})
            reply = "<strong>Payment Structure:</strong><br><br>"
            reply += f"• <strong>Advance Payment:</strong> {payment.get('mandatory_advance', '50% of total project value required to initiate production')}<br>"
            reply += f"• <strong>Final Payment:</strong> {payment.get('final_payment', 'Remaining balance due upon completion')}"
            return {"reply": reply, "citations": ["Source: Payment Terms"]}
        
        # Refund queries
        refund_keywords = ['refund', 'cancel', 'cancellation', 'money back', 'return', 'reimburs']
        if self._fuzzy_match(query_lower, refund_keywords):
            financial = self.knowledge_base.get('financial_terms', {})
            refund = financial.get('refund_policy', {})
            reply = "<strong>Refund Policy:</strong><br><br>"
            reply += f"• <strong>Before Confirmation:</strong> {refund.get('pre_confirmation', 'N/A')}<br>"
            reply += f"• <strong>After Confirmation:</strong> {refund.get('post_confirmation', 'No refunds once production begins')}<br>"
            reply += f"• <strong>Note:</strong> {refund.get('calculation_basis', 'All percentages calculated on full project price')}"
            return {"reply": reply, "citations": ["Source: Refund Policy"]}
        
        # Project workflow queries
        workflow_keywords = ['start', 'begin', 'process', 'workflow', 'work flow', 'how does', 'step', 'procedure', 'onboard']
        if self._fuzzy_match(query_lower, workflow_keywords):
            workflow = self.knowledge_base.get('operational_workflow', {})
            reply = "<strong>Project Workflow:</strong><br><br>"
            if workflow.get('onboarding'):
                reply += f"<strong>Onboarding:</strong> {workflow.get('onboarding')}<br><br>"
            stages = workflow.get('production_stages', [])
            if stages:
                reply += "<strong>Production Stages:</strong><br>"
                for stage in stages:
                    reply += f"{stage['step']}. <strong>{stage['name']}</strong>: {stage['desc']}<br>"
            return {"reply": reply, "citations": ["Source: Operational Workflow"]}
        
        # Contact/Support queries
        contact_keywords = ['contact', 'reach', 'email', 'phone', 'support', 'help', 'talk', 'speak']
        if self._fuzzy_match(query_lower, contact_keywords):
            reply = "<strong>Contact Us:</strong><br><br>"
            reply += "• <strong>WhatsApp:</strong> +919380962377<br>"
            reply += "• <strong>Email:</strong> royalvistatechsolutions@gmail.com<br>"
            reply += "• You can also use the contact form on our website to send us a message!"
            return {"reply": reply, "citations": ["Source: Contact Information"]}
        
        # TF-IDF similarity matching as fallback
        query_vec = self.vectorizer.transform([query_lower])
        similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
        
        # Lower threshold since we have keyword matching above
        if max(similarities) < 0.15:
            return None # Trigger out-of-scope fallback
        
        best_idx = similarities.argsort()[-1]
        response = self.chunks[best_idx]
        citation = self.citations[best_idx]
        
        # Clean the response for natural tone
        reply = response
        if "FAQ:" in reply:
            reply = reply.split("Answer:")[1].strip()
        elif "Service:" in reply:
            # Format service responses nicely
            parts = reply.split(".")
            service_name = parts[0].replace("Service:", "").strip()
            reply = f"<strong>{service_name}</strong><br><br>" + ".".join(parts[1:]).strip()
        elif "Payment Policy:" in reply:
            reply = reply.replace("Payment Policy:", "<strong>Payment Policy:</strong><br>")
        elif "Refund Policy:" in reply:
            reply = reply.replace("Refund Policy:", "<strong>Refund Policy:</strong><br>")
        elif "Company Info:" in reply:
            reply = reply.replace("Company Info:", "").strip()
        elif "Company Tagline:" in reply:
            reply = reply.replace("Company Tagline:", "<strong>Tagline:</strong> ").strip()
        
        return {
            "reply": reply,
            "citations": [citation]
        }

    def generate_job_structure(self, raw_text):
        """
        Structures a job posting from raw text using advanced heuristics.
        """
        # Rule-based Title Extraction
        title = "Job Opportunity"
        lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
        for line in lines[:3]: # Check first 3 lines
            if 10 < len(line) < 70:
                title = line
                break
        
        # Categories mapping
        found_cats = []
        keywords = {
            "2024 Passout": ["2024", "batch", "passout", "graduate"],
            "2025 Passout": ["2025", "batch", "passout", "graduate"],
            "Fresher": ["fresher", "no experience", "entry level", "entry-level"],
            "Experienced": ["experienced", "2 years", "3 years", "senior", "mid-level"],
            "Hackathons": ["hackathon", "competition", "coding contest", "challenge"]
        }
        for cat, keys in keywords.items():
            if any(k in raw_text.lower() for k in keys):
                found_cats.append(cat)

        # Better Description Structuring
        paragraphs = [p for p in raw_text.split('\n\n') if len(p.strip()) > 20]
        overview = paragraphs[0] if paragraphs else raw_text[:200]
        
        structured = f"""
        <h3>Role Overview</h3>
        <p>{overview}</p>
        
        <h3>Key Responsibilities</h3>
        <ul>
            <li>Contribute to the full development lifecycle of client projects.</li>
            <li>Maintain high standards of code quality and documentation.</li>
            <li>Collaborate with cross-functional teams to deliver innovative solutions.</li>
        </ul>

        <h3>Requirements</h3>
        <ul>
            <li>Strong problem-solving skills and attention to detail.</li>
            <li>Experience with modern tech stacks and industry best practices.</li>
            <li>Excellent communication and teamwork abilities.</li>
        </ul>
        """
        
        return {
            "title": title,
            "description": structured.strip(),
            "categories": found_cats,
            "eligible_years": ";".join(sorted(list(set(re.findall(r'20\d{2}', raw_text))))) or "Not Specified",
            "summary": raw_text[:250] + "...",
            "tags": ";".join(found_cats)
        }
