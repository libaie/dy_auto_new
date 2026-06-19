"""Content template and sensitive-word mutation use cases."""
from app.services.content_service import content_service


def create_template(db, request):
    return content_service.create_template(
        db,
        name=request.name,
        category=request.category,
        body=request.body,
        variables=request.variables,
    )


def list_templates(db, category=None, skip: int = 0, limit: int = 50):
    limit = min(limit, 100)
    templates, total = content_service.list_templates(db, category=category, skip=skip, limit=limit)
    return {"templates": templates, "total": total}


def get_template(db, template_id: str):
    return content_service.get_template(db, template_id)


def update_template(db, template_id: str, request):
    updates = request.model_dump(exclude_none=True)
    return content_service.update_template(db, template_id, **updates)


def delete_template(db, template_id: str):
    return content_service.delete_template(db, template_id)


def add_sensitive_word(db, request):
    return content_service.add_sensitive_word(db, request.word)


def list_sensitive_words(db, skip: int = 0, limit: int = 200):
    words, total = content_service.list_sensitive_words(db, skip=skip, limit=limit)
    return {"words": words, "total": total}


def delete_sensitive_word(db, word_id: str):
    return content_service.delete_sensitive_word(db, word_id)
