# Educational Story Generator 📚

A Python script that generates engaging educational stories for teachers to use when introducing new chapters to students. Perfect for creating compelling lesson plan introductions that connect with students emotionally while introducing educational topics.

## Features

- 🎯 **Customizable Stories**: Generate stories based on class level, chapter, topic, and desired emotion
- 📝 **Multiple Story Lengths**: Choose from short, medium, or long stories
- 💾 **Save Stories**: Option to save generated stories to text files
- 🎭 **Emotional Variety**: Support for various emotional tones (happy, sad, exciting, mysterious, etc.)
- 👥 **Age-Appropriate**: Content automatically adjusted for different grade levels

## Quick Start

```bash
# 1. Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone/download this project and navigate to directory
cd education-story-creation

# 3. Run the automated setup
./setup.sh

# 4. Edit .env file with your OpenAI API key

# 5. Generate your first story!
uv run story_generator.py
```

## Setup

This project uses `uv` for fast and reliable Python package management. Benefits include:

- **Speed**: `uv` is 10-100x faster than `pip`
- **Reliability**: Better dependency resolution and conflict detection
- **Reproducible builds**: `uv.lock` ensures exact same dependencies across environments
- **Modern workflow**: No need to manually manage virtual environments
- **Zero-config**: `uv run` executes commands without activating virtual environments

### 1. Install Dependencies

```bash
# Sync dependencies from pyproject.toml and create uv.lock
uv sync

# This will automatically:
# - Create a virtual environment (.venv)
# - Install all dependencies from pyproject.toml
# - Generate/update uv.lock file for reproducible builds
```

Alternatively, for development:

```bash
# Create virtual environment manually
uv venv

# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the project in editable mode
uv pip install -e .
```

### 2. Configure OpenAI API Key

1. Get your OpenAI API key from [OpenAI Platform](https://platform.openai.com/api-keys)
2. Copy `env_template.txt` to `.env`:
   ```bash
   cp env_template.txt .env
   ```
3. Edit `.env` and replace `your_openai_api_key_here` with your actual API key:
   ```
   OPENAI_API_KEY=sk-your-actual-api-key-here
   ```

## Usage

### Interactive Mode

Run the script and follow the prompts:

```bash
# Using uv run (recommended - no need to activate venv)
uv run story_generator.py

# Or using the installed command
uv run story-generator

# Or activate venv and run directly
source .venv/bin/activate
python story_generator.py
```

You'll be asked to provide:
- **Class/Grade Level**: e.g., "5th grade", "high school", "middle school"
- **Chapter**: The subject area or chapter name
- **Topic**: Specific topic or situation to focus on
- **Emotion**: Desired emotional tone for the story
- **Story Length**: short, medium, or long

### Example Usage

```
🎓 Educational Story Generator
========================================
Enter class/grade level (e.g., '5th grade', 'high school'): 7th grade
Enter chapter name or subject area: Mathematics - Fractions
Enter specific topic or situation: Adding fractions with different denominators
Enter desired emotion: exciting
Enter story length (default: medium): medium

🔄 Generating exciting story about 'Adding fractions with different denominators' for 7th grade students...

# Example with uv run (no venv activation needed):
uv run story_generator.py
```

### Programmatic Usage

You can also use the `StoryGenerator` class directly in your code:

```python
from story_generator import StoryGenerator

# Initialize the generator
generator = StoryGenerator()

# Generate a story
story = generator.generate_story(
    class_level="8th grade",
    chapter="Science - Photosynthesis",
    topic="How plants make their own food",
    emotion="mysterious",
    story_length="medium"
)

print(story)

# Save the story
filename = generator.save_story(story)
print(f"Story saved to: {filename}")
```

## Emotion Options

The following emotional tones are supported:
- **happy**: Upbeat, positive stories
- **sad**: Touching, emotional stories that create empathy
- **exciting**: Action-packed, thrilling narratives
- **mysterious**: Intriguing stories that build curiosity
- **inspiring**: Motivational stories that encourage learning
- **adventurous**: Exploration and discovery themes
- **funny**: Humorous stories that make learning fun
- **dramatic**: Intense stories with compelling conflicts

## Story Length Options

- **short**: 2-3 paragraphs (150-200 words) - Quick introductions
- **medium**: 4-5 paragraphs (300-400 words) - Standard lesson starters
- **long**: 6-8 paragraphs (500-600 words) - Detailed storytelling

## Educational Benefits

- **Engagement**: Stories capture student attention better than direct instruction
- **Emotional Connection**: Different emotions help students connect with material
- **Context Setting**: Stories provide real-world context for abstract concepts
- **Memory Aid**: Narrative structures help students remember key concepts
- **Universal Appeal**: Works across different subjects and grade levels

## File Structure

```
education-story-creation/
├── story_generator.py    # Main script
├── pyproject.toml       # Modern Python project configuration
├── uv.lock              # Lockfile for reproducible builds (auto-generated)
├── env_template.txt     # Example environment configuration
├── example_usage.py     # Example usage script
├── setup.sh            # Automated setup script
├── README.md           # This file
├── .venv/              # Virtual environment (created by uv)
└── .env                # Your actual API key (not tracked in git)
```

## Example Generated Stories

### Mathematics Example
*Input: 5th grade, Multiplication, Times tables, Happy*

> "Maya loved collecting stickers, and today was extra special because her grandmother had given her 6 packs of animal stickers. Each pack contained exactly 8 stickers! 'How many stickers do I have altogether?' Maya wondered excitedly..."

### Science Example
*Input: 8th grade, Physics, Gravity, Mysterious*

> "Alex couldn't believe what they were seeing. The old pocket watch their great-grandfather had left them was floating in mid-air, completely defying everything they thought they knew about gravity..."

## Tips for Teachers

1. **Pre-lesson Engagement**: Use stories at the beginning of lessons to grab attention
2. **Differentiated Learning**: Adjust emotion and complexity based on your class
3. **Discussion Starters**: Use stories to prompt questions and discussions
4. **Cross-curricular Connections**: Generate stories that connect multiple subjects
5. **Cultural Sensitivity**: Review generated content to ensure appropriateness

## Troubleshooting

### Common Issues

**Error: "OPENAI_API_KEY not found"**
- Make sure you've created a `.env` file with your API key
- Check that the API key is correctly formatted (starts with `sk-`)

**API Rate Limits**
- OpenAI has usage limits based on your account type
- Consider upgrading your OpenAI plan for higher limits

**Story Quality Issues**
- Try different emotional tones or rephrasing your topic
- Experiment with story length options
- Provide more specific topic descriptions

## License

This project is open source and available under the MIT License.

## Contributing

Feel free to submit issues, feature requests, or pull requests to improve the story generator! 
## API Endpoints

### Difficult Word API

The project now includes an API endpoint that can extract text from PDFs and generate educational flashcards.

#### Setup

1. **Install dependencies**:
   ```bash
   uv sync
   ```

2. **Configure environment variables** in `.env`:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   OPENAI_MODEL=gpt-3.5-turbo
   MISTRAL_API_KEY=your_mistral_api_key_here  # Optional
   ```

3. **Start the API server**:
   ```bash
   uv run difficult_word.py
   ```

#### API Endpoints

- **GET /** - Root endpoint
- **GET /health** - Health check
- **POST /api/education/word-meaning** - Generate flashcards from PDF

#### Usage Example

```bash
# Test the API
uv run test_api.py

# Send a PDF file to generate flashcards
curl -X POST "http://127.0.0.1:8000/api/education/word-meaning" \
     -F "files=@your_document.pdf"
```

#### Response Format

The API returns flashcards in this format:

```json
{
    "flashcards": {
        "1": {
            "term": "Key Term 1",
            "definition": "Clear and concise definition of the term",
            "example": "Example or usage of the term"
        },
        "2": {
            "term": "Key Term 2",
            "definition": "Clear and concise definition of the term", 
            "example": "Example or usage of the term"
        }
    }
}
```

#### Features

- **PDF Processing**: Converts PDF to images for text extraction
- **AI-Powered Flashcards**: Uses OpenAI to generate educational content
- **Structured Output**: Returns well-formatted JSON responses
- **Error Handling**: Graceful error handling and fallbacks
- **Temporary File Management**: Automatic cleanup of temporary files
