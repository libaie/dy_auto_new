"""Content generation use cases."""
from app.domains.content_collection.content_service import content_service


async def generate_from_template(db, request):
    return await content_service.generate_from_template(
        db,
        request.template_id,
        request.context,
    )


async def generate_keywords(db, request):
    return await content_service.generate_keyword_matrix(
        request.keyword,
        request.count,
        db=db,
    )


async def generate_regex(db, request):
    return await content_service.generate_regex(db, request.description)


async def generate_clean_prompt(db, request):
    return await content_service.generate_clean_prompt(db, request.description)
