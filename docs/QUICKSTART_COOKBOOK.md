# 🍳 Quick Start Cookbook: 5-Minute Agent Recipes

Welcome to the SentientResearchAgent cookbook! This guide contains ready-to-use "recipes" for creating powerful agents in just 5 minutes. No technical knowledge required—just copy, paste, and customize!

## 🎯 "Vibe Prompting": Just Say What You Want

With SentientResearchAgent, you don't need to understand the technical details. Just describe what you want in natural language, and the framework handles the rest. We call this "**Vibe Prompting**"—you provide the vibe, we build the agent!

## 📚 Table of Contents

1. [Getting Started](#getting-started)
2. [Content Creation Recipes](#content-creation-recipes)
3. [Analysis & Research Recipes](#analysis--research-recipes)
4. [Creative Writing Recipes](#creative-writing-recipes)
5. [Business & Professional Recipes](#business--professional-recipes)
6. [Technical Recipes](#technical-recipes)
7. [Fun & Experimental Recipes](#fun--experimental-recipes)
8. [Customization Tips](#customization-tips)

## 🚀 Getting Started

### Basic Setup (One Time Only)

```bash
# 1. Clone and setup (5 minutes)
git clone https://github.com/yourusername/SentientResearchAgent.git
cd SentientResearchAgent
./setup.sh

# 2. Add your API key to .env file
echo "OPENROUTER_API_KEY=your-key-here" > .env

# 3. Start the agent
python -m sentientresearchagent
```

### Your First Agent

```python
from sentientresearchagent import SentientAgent

agent = SentientAgent.create()
result = await agent.run("Your request here")
print(result)
```

## 🎙️ Content Creation Recipes

### Recipe 1: Podcast Generator

**What it does**: Creates complete podcast episodes with intro, segments, and outro.

```python
# The Vibe
request = """
Create a 10-minute podcast episode about artificial intelligence in healthcare.
Make it engaging for a general audience, include 3 main segments, and add
timestamps for each section.
"""

# The Magic
agent = SentientAgent.create()
podcast = await agent.run(request)

# What you get:
# - Complete script with host dialogue
# - 3 well-researched segments
# - Timestamps for each section
# - Suggested background music cues
# - Show notes for posting
```

**Breakdown of what happens**:
1. **SEARCH**: Latest AI healthcare developments
2. **THINK**: Select most interesting topics for general audience
3. **WRITE**: Episode structure and outline
4. **SEARCH**: Deep dive into selected topics
5. **WRITE**: Full script with natural dialogue
6. **THINK**: Review and add engagement elements
7. **WRITE**: Final script with timestamps and show notes

### Recipe 2: Blog Post Factory

**What it does**: Generates SEO-optimized blog posts on any topic.

```python
# The Vibe
request = """
Write a blog post about sustainable living tips for city dwellers.
Make it practical, include 10 actionable tips, and optimize for SEO
with the keyword "urban sustainability".
"""

# The Magic
agent = SentientAgent.create()
blog_post = await agent.run(request)

# What you get:
# - SEO-optimized title and meta description
# - Engaging introduction
# - 10 detailed, actionable tips
# - Conclusion with call-to-action
# - Related keywords and tags
```

### Recipe 3: YouTube Script Writer

**What it does**: Creates engaging video scripts with hooks, content, and CTAs.

```python
# The Vibe
request = """
Create a YouTube script for a 5-minute video about "5 Mind-Blowing 
Space Facts You Never Knew". Include a hook, smooth transitions,
and remind viewers to subscribe.
"""

# The Magic
agent = SentientAgent.create()
video_script = await agent.run(request)

# What you get:
# - Attention-grabbing hook (first 15 seconds)
# - 5 fascinating space facts with explanations
# - Visual cue suggestions
# - Transition phrases
# - Subscribe reminder and end screen text
```

## 📊 Analysis & Research Recipes

### Recipe 4: Market Analyzer

**What it does**: Comprehensive market analysis with actionable insights.

```python
# The Vibe
request = """
Analyze the electric vehicle market for potential investment opportunities.
Include major players, growth trends, challenges, and give me 3 specific
investment recommendations with risk levels.
"""

# The Magic
agent = ProfiledSentientAgent.create_with_profile("market_analyzer")
analysis = await agent.run(request)

# What you get:
# - Market size and growth projections
# - Key players analysis (Tesla, BYD, etc.)
# - Technology trends
# - Regulatory landscape
# - 3 specific investment recommendations
# - Risk assessment for each
```

### Recipe 5: Competitor Intelligence

**What it does**: Deep dive into competitor strategies and opportunities.

```python
# The Vibe
request = """
Analyze Starbucks' digital strategy and identify 3 opportunities
for a small coffee shop to compete effectively using technology.
"""

# The Magic
agent = SentientAgent.create()
intel = await agent.run(request)

# What you get:
# - Starbucks digital strategy breakdown
# - Their app features and loyalty program analysis
# - 3 specific tech opportunities for small shops
# - Implementation suggestions
# - Cost-benefit analysis
```

### Recipe 6: Crypto Market Scanner

**What it does**: Analyzes cryptocurrency trends and opportunities.

```python
# The Vibe
request = """
Scan the crypto market for emerging DeFi projects with strong fundamentals.
Focus on projects under $100M market cap with real utility. Give me
top 5 picks with analysis.
"""

# The Magic
agent = ProfiledSentientAgent.create_with_profile("crypto_analytics_agent")
crypto_picks = await agent.run(request)

# What you get:
# - Market overview and DeFi trends
# - 5 promising projects under $100M cap
# - Utility analysis for each
# - Team and tokenomics review
# - Risk factors and potential returns
```

## 📖 Creative Writing Recipes

### Recipe 7: Story Generator

**What it does**: Creates complete short stories with rich characters and plot.

```python
# The Vibe
request = """
Write a short story about a robot who discovers it can dream.
Make it emotional and thought-provoking, around 2000 words.
Include themes of consciousness and identity.
"""

# The Magic
agent = SentientAgent.create()
story = await agent.run(request)

# What you get:
# - Complete 2000-word story
# - Well-developed robot protagonist
# - Emotional character arc
# - Philosophical themes woven throughout
# - Satisfying conclusion
```

### Recipe 8: Children's Book Creator

**What it does**: Generates children's stories with moral lessons.

```python
# The Vibe
request = """
Create a children's story about a shy turtle who wants to make friends.
Age 4-7, include a gentle lesson about being yourself. Add suggestions
for illustrations on each page.
"""

# The Magic
agent = SentientAgent.create()
childrens_book = await agent.run(request)

# What you get:
# - Complete story with simple language
# - Character: Timmy the Turtle
# - Gentle friendship lesson
# - 10-12 pages with illustration notes
# - Reading guide for parents
```

### Recipe 9: World Builder

**What it does**: Creates detailed fictional worlds for games or stories.

```python
# The Vibe
request = """
Design a fantasy world where magic is powered by music. Include
geography, different kingdoms, magic system rules, and major conflicts.
Make it suitable for a D&D campaign.
"""

# The Magic
agent = SentientAgent.create()
world = await agent.run(request)

# What you get:
# - Detailed world map description
# - 5 unique kingdoms with cultures
# - Music-based magic system rules
# - Political conflicts and tensions
# - Notable NPCs and plot hooks
# - DM resources and tables
```

## 💼 Business & Professional Recipes

### Recipe 10: Business Plan Generator

**What it does**: Creates professional business plans for any idea.

```python
# The Vibe
request = """
Create a business plan for a mobile dog grooming service in Seattle.
Include market analysis, financial projections for year 1, and 
marketing strategy. Make it investor-ready.
"""

# The Magic
agent = SentientAgent.create()
business_plan = await agent.run(request)

# What you get:
# - Executive summary
# - Market analysis with Seattle specifics
# - Service offerings and pricing
# - Year 1 financial projections
# - Marketing strategy (digital + local)
# - Operations plan
# - Funding requirements
```

### Recipe 11: Grant Proposal Writer

**What it does**: Writes compelling grant proposals for funding.

```python
# The Vibe
request = """
Write a grant proposal for a community garden project that teaches
urban farming to low-income families. Requesting $50,000 from
environmental foundations. Make it compelling with clear impact metrics.
"""

# The Magic
agent = SentientAgent.create()
proposal = await agent.run(request)

# What you get:
# - Executive summary with hook
# - Problem statement with statistics
# - Proposed solution and activities
# - Budget breakdown for $50,000
# - Impact metrics and evaluation plan
# - Sustainability plan
```

### Recipe 12: Product Launch Strategist

**What it does**: Creates comprehensive product launch plans.

```python
# The Vibe
request = """
Plan a product launch for a new meditation app targeting busy professionals.
Include pre-launch, launch, and post-launch strategies with timelines
and KPIs.
"""

# The Magic
agent = SentientAgent.create()
launch_plan = await agent.run(request)

# What you get:
# - 90-day launch timeline
# - Pre-launch: Beta testing, influencer outreach
# - Launch: PR strategy, launch events
# - Post-launch: User retention tactics
# - Marketing channels and budget
# - Success KPIs and tracking
```

## 💻 Technical Recipes

### Recipe 13: API Designer

**What it does**: Designs REST APIs with full documentation.

```python
# The Vibe
request = """
Design a REST API for a task management system. Include user authentication,
CRUD operations for tasks, and team collaboration features. Provide
OpenAPI specification.
"""

# The Magic
agent = SentientAgent.create()
api_design = await agent.run(request)

# What you get:
# - Complete API endpoint design
# - Authentication flow
# - Request/response examples
# - OpenAPI/Swagger specification
# - Database schema suggestions
# - Security best practices
```

### Recipe 14: Code Documenter

**What it does**: Generates comprehensive documentation for codebases.

```python
# The Vibe
request = """
Create user documentation for a Python library that handles data validation.
Include installation, quick start, API reference, and common use cases.
Make it beginner-friendly.
"""

# The Magic
agent = SentientAgent.create()
documentation = await agent.run(request)

# What you get:
# - Installation instructions
# - Quick start guide with examples
# - Complete API reference
# - 5 common use cases with code
# - Troubleshooting section
# - Contributing guidelines
```

### Recipe 15: Architecture Advisor

**What it does**: Provides system architecture recommendations.

```python
# The Vibe
request = """
Recommend a scalable architecture for a social media app expecting
1 million users. Include tech stack, database choices, caching strategy,
and estimated AWS costs.
"""

# The Magic
agent = SentientAgent.create()
architecture = await agent.run(request)

# What you get:
# - High-level architecture diagram description
# - Tech stack recommendations
# - Database: PostgreSQL + Redis
# - Caching and CDN strategy
# - Microservices breakdown
# - AWS cost estimation
# - Scaling considerations
```

## 🎮 Fun & Experimental Recipes

### Recipe 16: Recipe Creator (Meta!)

**What it does**: Creates actual cooking recipes based on ingredients.

```python
# The Vibe
request = """
I have chicken, coconut milk, curry powder, and vegetables. Create a
delicious dinner recipe that takes under 30 minutes. Include tips
for making it restaurant-quality.
"""

# The Magic
agent = SentientAgent.create()
recipe = await agent.run(request)

# What you get:
# - Complete recipe with measurements
# - Step-by-step instructions
# - Prep and cook time
# - Pro tips for flavor
# - Serving suggestions
# - Nutritional information
```

### Recipe 17: Travel Itinerary Planner

**What it does**: Creates detailed travel plans for any destination.

```python
# The Vibe
request = """
Plan a 5-day trip to Tokyo for a couple interested in food and culture.
Budget: $3000 total. Include daily itineraries, restaurant recommendations,
and transportation tips.
"""

# The Magic
agent = SentientAgent.create()
itinerary = await agent.run(request)

# What you get:
# - Day-by-day itinerary
# - Must-visit cultural sites
# - Restaurant recommendations by area
# - Transportation guide and tips
# - Budget breakdown
# - Packing suggestions
# - Basic Japanese phrases
```

### Recipe 18: Personal Trainer

**What it does**: Creates customized workout and nutrition plans.

```python
# The Vibe
request = """
Create a 4-week fitness plan for a beginner wanting to lose 10 pounds.
Include workouts, meal plans, and motivational tips. No gym required,
just home exercises.
"""

# The Magic
agent = SentientAgent.create()
fitness_plan = await agent.run(request)

# What you get:
# - 4-week progressive workout plan
# - Home exercises with form tips
# - Daily meal plans with recipes
# - Shopping lists
# - Progress tracking suggestions
# - Motivational strategies
```

## 🛠️ Customization Tips

### Making Agents Your Own

1. **Be Specific**: The more details you provide, the better the output
   ```python
   # Good
   "Create a podcast about AI for beginners, 10 minutes, friendly tone"
   
   # Better
   "Create a 10-minute podcast about AI for complete beginners, explaining
   like they're 5, with funny analogies and a warm, encouraging tone"
   ```

2. **Add Constraints**: Set boundaries for more focused results
   ```python
   request = """
   Write a blog post about coffee, but:
   - Maximum 800 words
   - Include 5 scientific facts
   - Avoid mentioning Starbucks
   - Target health-conscious readers
   """
   ```

3. **Request Specific Formats**: Ask for the output structure you need
   ```python
   request = """
   Analyze Tesla stock and give me:
   1. Bullet points for quick reading
   2. One paragraph executive summary
   3. Three specific action items
   4. Risk level on scale of 1-10
   """
   ```

4. **Chain Requests**: Build on previous outputs
   ```python
   # First request
   outline = await agent.run("Create an outline for a mystery novel")
   
   # Follow-up request
   chapter = await agent.run(f"Based on this outline: {outline}, 
                            write Chapter 1 with a strong hook")
   ```

### Advanced Patterns

**Pattern 1: The Iterative Refiner**
```python
first_draft = await agent.run("Write a sales email for my SaaS product")
final_draft = await agent.run(f"Improve this email: {first_draft}. 
                              Make it more persuasive and add urgency")
```

**Pattern 2: The Multi-Perspective Analyzer**
```python
request = """
Analyze cryptocurrency regulation from three perspectives:
1. Government viewpoint
2. Crypto enthusiast viewpoint  
3. Traditional banker viewpoint
Then synthesize a balanced conclusion.
"""
```

**Pattern 3: The Depth Controller**
```python
# Quick overview
quick = await agent.run("Give me a 1-minute overview of quantum computing")

# Deep dive
detailed = await agent.run("Explain quantum computing in detail with 
                          examples, history, current state, and future")
```

## 🚀 Start Building Now!

Remember: **If you can describe it, SentientResearchAgent can build it!**

The patterns are simple:
- **SEARCH** when you need information
- **THINK** when you need analysis or decisions  
- **WRITE** when you need content creation

These combine automatically based on your request. You don't need to specify them—just describe what you want!

### Next Steps

1. Pick a recipe that matches your needs
2. Copy the code and customize the request
3. Run it and see the magic happen
4. Iterate and refine based on results
5. Share your amazing agents with the community!

Happy agent building! 🎉

---

**Pro Tip**: Start simple, then add complexity. Your first agent doesn't need to be perfect—it just needs to be useful to you!