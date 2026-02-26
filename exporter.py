import os
from pptx import Presentation
from pptx.util import Inches, Pt
from config import UPLOAD_DIR
from models import Portfolio, User

def generate_portfolio_ppt(portfolio: Portfolio, owner: User) -> str:
    """Generates a PowerPoint presentation from a Portfolio and returns its path."""
    prs = Presentation()
    
    # Slide 1: Title Slide
    title_slide_layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(title_slide_layout)
    title = slide.shapes.title
    subtitle = slide.placeholders[1]
    
    title.text = portfolio.name or owner.username
    subtitle.text = f"{portfolio.role or 'Professional Portfolio'}\n\n{portfolio.tagline or ''}"
    
    # Slide 2: About Me (Bio)
    if portfolio.bio:
        bullet_slide_layout = prs.slide_layouts[1]
        slide = prs.slides.add_slide(bullet_slide_layout)
        shapes = slide.shapes
        title_shape = shapes.title
        body_shape = shapes.placeholders[1]
        
        title_shape.text = "About Me"
        tf = body_shape.text_frame
        tf.text = portfolio.bio
        
    # Slide 3: Skills
    if portfolio.skills:
        bullet_slide_layout = prs.slide_layouts[1]
        slide = prs.slides.add_slide(bullet_slide_layout)
        shapes = slide.shapes
        title_shape = shapes.title
        body_shape = shapes.placeholders[1]
        
        title_shape.text = "Skills & Expertise"
        tf = body_shape.text_frame
        
        if isinstance(portfolio.skills, list):
            for skill in portfolio.skills:
                p = tf.add_paragraph()
                p.text = str(skill)
        elif isinstance(portfolio.skills, dict):
            for cat, skills in portfolio.skills.items():
                p = tf.add_paragraph()
                p.text = f"{cat}: {', '.join(skills)}"
        
    # Slide 4: Experience
    if portfolio.experience:
        bullet_slide_layout = prs.slide_layouts[1]
        slide = prs.slides.add_slide(bullet_slide_layout)
        shapes = slide.shapes
        title_shape = shapes.title
        body_shape = shapes.placeholders[1]
        
        title_shape.text = "Experience"
        tf = body_shape.text_frame
        
        if isinstance(portfolio.experience, list):
            for exp in portfolio.experience:
                title_str = exp.get("title", "")
                company = exp.get("company", "")
                dates = exp.get("dates", "")
                p = tf.add_paragraph()
                p.text = f"{title_str} at {company} ({dates})"
                p.level = 0
                
                desc = exp.get("description", "")
                if desc:
                    p2 = tf.add_paragraph()
                    p2.text = desc
                    p2.level = 1

    # Slide 5: Projects
    if portfolio.projects:
        bullet_slide_layout = prs.slide_layouts[1]
        slide = prs.slides.add_slide(bullet_slide_layout)
        shapes = slide.shapes
        title_shape = shapes.title
        body_shape = shapes.placeholders[1]
        
        title_shape.text = "Projects"
        tf = body_shape.text_frame
        
        if isinstance(portfolio.projects, list):
            for proj in portfolio.projects:
                p = tf.add_paragraph()
                p.text = proj.get("name", "Project")
                p.level = 0
                
                desc = proj.get("description", "")
                if desc:
                    p2 = tf.add_paragraph()
                    p2.text = desc
                    p2.level = 1
                    
    # Slide 6: Contact
    bullet_slide_layout = prs.slide_layouts[1]
    slide = prs.slides.add_slide(bullet_slide_layout)
    shapes = slide.shapes
    title_shape = shapes.title
    body_shape = shapes.placeholders[1]
    
    title_shape.text = "Contact Information"
    tf = body_shape.text_frame
    
    p = tf.add_paragraph()
    p.text = f"Email: {owner.email}"
    
    if portfolio.contact and isinstance(portfolio.contact, dict):
        for key, val in portfolio.contact.items():
            if val:
                p = tf.add_paragraph()
                p.text = f"{key.title()}: {val}"

    # Save presentation
    filename = f"{owner.username}_portfolio_{portfolio.id}.pptx"
    filepath = os.path.join(UPLOAD_DIR, filename)
    prs.save(filepath)
    
    return filepath
