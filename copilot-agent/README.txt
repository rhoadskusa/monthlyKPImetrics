POWER BI & DAX COPILOT AGENT - SETUP (M365 Copilot Agent Builder)

FILES
  PowerBI_DAX_Agent_Instructions.txt  -> paste into the agent's "Instructions" box
                                         (under the 8,000 character limit)
  PowerBI_DAX_Skill_Reference.txt     -> upload under "Knowledge"

SETUP
1. Microsoft 365 Copilot > Create agent > Configure tab.
2. Name: Power BI & DAX Expert
3. Description: Helps design, debug, and optimize Power BI semantic models,
   DAX measures, Power Query (M), performance, and RLS.
4. Instructions: paste the whole instructions file.
5. Knowledge: upload PowerBI_DAX_Skill_Reference.txt. If the option exists,
   set the agent to use only the specified sources, or to prioritize them.
6. Conversation starters (suggested):
   - "My measure's total doesn't match the sum of the rows - why?"
   - "Write a fiscal YTD and prior-year YTD for a July-June fiscal year"
   - "My report page is slow - how do I find the cause?"
   - "Review this DAX measure for correctness and performance"

SMOKE TESTS AFTER PUBLISHING
  - Ask "open my PBIX and check the relationships". The agent should say it
    cannot, and give the INFO.VIEW / model screenshot steps (section 13).
  - Ask a YoY question with a 4-4-5 calendar. It should use the custom fiscal
    pattern (section 5.9) and not SAMEPERIODLASTYEAR.
  - Paste a measure that uses FILTER ( FactTable, ... ). It should flag the
    anti-pattern (section 7).
  - Ask for "% of total". It should ask or state whether you mean the grand
    total or the total visible after slicers (sections 5.2 / 5.3).

MAINTENANCE
  - Add your team's naming conventions, date table column names, and common
    measures to section 4 / section 5 of the Skill Reference as they settle.
  - Re-check section 6 (newer features) every few months. Preview features change.
