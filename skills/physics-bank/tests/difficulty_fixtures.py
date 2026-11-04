"""Hand-authored complete TIMBAD audit fixture for validator tests."""
def rating(level=3):
    return {
        "rubric_id": "pocket-cosmos-timbad", "rubric_version": "1.0",
        "level": level, "overall_level": f"L{level}",
        "review_status": "APPROVED", "rejection_reason": None,
        "question_quality_flags": [],
        "drivers": ["Independently organize force decomposition and acceleration equations."],
        "overall_reason": "Force decomposition and Newton's law form a standard multistep route.",
        "boundary_reason": "Requires organizing steps beyond substitution; no complex model combination.",
        "timbad": {
            "T": {"score": 0, "rationale": "Acceleration is explicitly requested.", "evidence": "Find acceleration."},
            "I": {"score": 0, "rationale": "Angle and smooth surface are explicit.", "evidence": "Smooth incline at theta."},
            "M": {"score": 1, "rationale": "Choose the along-slope axis.", "evidence": "Gravity and normal act on the block."},
            "B": {"score": 1, "rationale": "Resolve gravity then apply Newton's law.", "evidence": "mg sin(theta) = ma."},
            "A": {"score": 0, "rationale": "Cancel mass.", "evidence": "a = g sin(theta)."},
            "D": {"score": 0, "rationale": "Check units and direction.", "evidence": "Acceleration points downhill."},
        },
        "primary_bottleneck": "M", "secondary_bottleneck": "B",
        "key_insights": [], "insight_depth": "NONE",
        "solution_outline": ["Resolve gravity along slope; use mg sin(theta) = ma.", "Check downhill acceleration and units."],
        "final_answer": "a = g sin(theta)",
        "topic": "Dynamics", "subtopic": "Inclined planes",
        "prerequisites": ["Newton's second law", "Force components"],
        "key_skills": ["Free Body Diagram", "Force Decomposition"],
        "math_tools": ["Trigonometry", "Algebra"],
        "rating_confidence": "HIGH", "needs_human_review": False,
        "review_notes": "", "assessed_at": None, "reviewer": None,
    }
