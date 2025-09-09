# # main.py
# from fastapi import FastAPI
# from routers import auth, profile, dashboard, vocabulary, grammar, reading, writing, speaking
# import uvicorn

# app = FastAPI(title="Education / Language Learning API")

# # Include routers
# app.include_router(auth.router)
# app.include_router(profile.router)
# app.include_router(dashboard.router)
# app.include_router(vocabulary.router)
# app.include_router(grammar.router)
# app.include_router(reading.router)
# app.include_router(writing.router)
# app.include_router(speaking.router)


# # Run: uvicorn main:app --reload
# if __name__ == "__main__":
#     uvicorn.run("language_learning_apis:app", host="127.0.0.1", port=8001, reload=True)