# ASR-7 Scientific Paper Roadmap

## Title (Example)
**"Layered Embodied Agency: A Behavior-Based Architecture for Character-Driven AI Companions"**

---

## Research Focus Areas

1. **Separation of symbolic vs. concrete reasoning**
   - Cognitive layer handles **goals/emotions**  
   - Motion controllers handle **hardware primitives / body execution**  
   - Goal: Show benefits of abstraction in agent believability and modularity

2. **Utility-based behavior selection**
   - How the `BehaviorArbiter` chooses behaviors based on **cognitive state utility scores**  
   - Compare to **rule-based systems**  
   - Goal: Analyze **character consistency and emergent behavior**

3. **Virtual body representation**
   - Maintaining body state **separate from hardware**  
   - Includes posture, luminance, hand states, head orientation  
   - Goal: Show how virtual embodiment supports **consistent behavior and personality expression**

4. **Comparison to traditional chatbots**
   - Measure **user engagement and perceived believability**  
   - Compare embodied agents to **disembodied text-based agents**  

---

## Research Questions

- Does separating cognitive intent from physical expression improve agent believability?  
- How does utility-based behavior arbitration compare to rule-based systems for **character consistency**?  
- Can **emergent behaviors** arise from interacting utility scores?  
- How does virtual embodiment impact **user engagement** compared to standard chatbots?  

---

## Paper Structure (Suggested)

### 1. Abstract
- 2–3 sentences summarizing:
  - Motivation: why embodied AI matters  
  - Contribution: ASR-7 architecture  
  - Key findings or hypotheses  

### 2. Introduction
- Introduce **embodied AI** and its significance  
- Explain the gap in current research (chatbots are disembodied / non-reactive)  
- Present ASR-7 as a **case study / system implementation**  

### 3. Related Work
- Subsumption architectures (Brooks, 1986)  
- Behavior-based robotics  
- LLM-driven chatbots / agents  
- Virtual companions and multimodal AI  
- Goal: situate ASR-7 in the **current AI research landscape**  

### 4. Methods / Architecture
- **Layered architecture diagram**: Cognitive → Behavioral → Motion  
- **Data flow diagram**  
- Explain **Cognitive Layer, Behavior Layer, Virtual Body, Motion Controller**  
- Detail **utility score calculation and behavior selection**  
- Explain **mood, memory, and emergent behavior mechanisms**  

### 5. Experiments / Evaluation Plan
- **User study:** Compare ASR-7 vs. disembodied chatbot
  - Metrics: believability, engagement, perceived personality, dialogue richness  
- **Ablation studies:** 
  - Remove utility-based behavior → measure consistency drop  
  - Remove mood influence → measure effect on personality  
- **Quantitative logging:** 
  - Frequency of behavior selection, cognitive-body alignment, emergent behavior patterns  

### 6. Results (Expected / Placeholder)
- Tables / charts showing:
  - Behavior consistency metrics  
  - User engagement scores  
  - Emergent behavior examples  
- Screenshots or session logs if helpful  

### 7. Discussion
- Interpret results: does separation of cognition/motion improve believability?  
- Explain patterns in emergent behaviors  
- Discuss limitations and possible biases  
- Suggest future improvements (head tracking, multimodal understanding, RL integration)  

### 8. Conclusion
- Recap contributions of ASR-7  
- Highlight significance for **AI agent research**  
- Suggest pathways for further studies  

---

## Metrics & Evaluation Suggestions

| Metric                        | Method / Tool                                |
|--------------------------------|---------------------------------------------|
| Believability                  | User survey, Likert scale (1–5)            |
| Engagement                     | Interaction duration, message count         |
| Character consistency          | Behavior selection logs, emotion matching  |
| Emergent behavior frequency    | Unexpected yet coherent behavior occurrences |
| Mood influence effectiveness   | Compare sessions with vs. without mood impact |

---

## Advice / Things to Do

1. **Draw diagrams early**
   - Layered architecture  
   - Data flows  
   - Behavior arbitration logic  

2. **Plan user study / evaluation**
   - Recruit 5–20 participants  
   - Use ASR-7 vs. a baseline chatbot  
   - Collect both **quantitative metrics** and **qualitative feedback**  

3. **Document ASR-7 architecture clearly**
   - Keep code references for each layer  
   - Highlight **unique contributions** (utility-based behaviors, emergent personality)  

4. **Write clearly about novelty**
   - Focus on **behavior emergence, modular separation, and embodied design**  
   - Explain why these features are **better than existing chatbots / agents**

5. **Collect examples / logs**
   - Real session dialogues  
   - Behavior selection tables  
   - Mood evolution traces  

6. **Iterative writing**
   - Start with **Methods and Architecture**, then Introduction/Related Work  
   - Abstract and Conclusion last  

---

## References / Reading Suggestions

- Brooks, R. A. (1986). *A Robust Layered Control System for a Mobile Robot.* IEEE Journal of Robotics and Automation.  
- Subsumption Architecture literature  
- Recent papers on **embodied AI agents** and **multimodal LLM systems**  
- Chatbot user engagement studies  
- Papers on **utility-based behavior selection**  

---

## Optional Enhancements

- Include a **video demo link** of ASR-7  
- Highlight **novel emergent behaviors** with screenshots  
- Compare **different behavior selection strategies** quantitatively  
- Discuss implications for **autonomous agent safety / alignment**  

---

**Status:** Drafted, ready to start architecture diagrams and experiment planning.  
**Next steps:**  
1. Draw architecture diagrams  
2. Define experiment protocol & metrics  
3. Write Methods / Architecture section  
4. Begin Related Work section  

