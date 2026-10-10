# Project Vision

What the app is for, so design and engineering choices can be judged against it. The canonical design is in `CONTEXT.md` and `docs/system-design/`.

## The app

A personal notebook for one learner who is taking a Spanish class as a complete beginner. It is where they compile Spanish they meet: vocab and tips the teacher gives the class, and words and phrases native speakers use in conversation. Each one is noted with its translation and, where useful, its context.

It sits beside the learner's other resources (the class materials and Lingvist), not in place of them. It is not a learning platform, and it does not try to rebuild Lingvist or Duolingo.

Design pillars:
- **Capture is fast.** Noting something down mid-class or mid-conversation takes seconds: the Spanish and its translation, nothing more required.
- **Enrichment comes later.** Context, such as formal or informal register, can be added afterwards, when there is time.
- **Recap is a light layer on top.** The learner can go back over what they have noted, flashcard-style. Recap serves the notebook; it is not an adaptive course.

Judge a design decision by whether it keeps capture fast and keeps the notebook the learner's own.

## How the owner works

The owner delegates heavily and wants momentum with visibility. Design concerns are kept separate from technology choices, and the design is settled iteratively (see [delivery workflow](delivery-workflow.md)).
