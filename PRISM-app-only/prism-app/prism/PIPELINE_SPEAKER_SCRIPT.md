# PRISM pipeline — speaker script

16 slides, about 8 minutes spoken. The same notes are embedded in the PPTX;
this file is for printing or a second screen.

## 1. PRISM

Open cold. Do not introduce yourself yet. Say: 'A building came down in Satya Niketan. Nineteen people inside. The commander had a pile, a phone, and no idea where to start. This is the chain we built to answer that.' Then advance. Total deck is about 9 minutes.

## 2. A rescue commander has five questions and about six hours of light

Frame the problem as questions, not technology. A commander does not want a dashboard. He wants to know which pile to start with. Read the five questions out loud, then point at the right-hand column: each one is a stage that exists in code. Land the last line — the system prints its own error rate, which almost nothing in this space does.

## 3. Seven stages, one chain, three inputs

This is the slide people photograph. Trace it left to right with your hand. Three inputs: municipal records, satellite, and a sensor in the structural element. Seven stages. The output is not a map — it is an ordered list with times on it. The return arrow is the part that matters: allocation is recomputed as the survival clock runs, so the plan changes by itself without anyone re-entering data.

## 4. 0.976

This is the only stage that runs before the disaster. Two ratios, multiplied: floors built over floors sanctioned, times people living there over people the plan was designed for. At Satya Niketan that is three times on the floors and three and a half times on the density. I quote the floor ratio, because it is the conservative one. Demand over capacity lands at two. Above one, it has already failed. No earthquake required, no satellite required.

## 5. 0.46 px

Be ruthless here — judges have heard 'we use satellite imagery' before. The plot at Satya Niketan is under half a pixel of the free Sentinel-2 image. Free imagery physically cannot see the sixth floor. What it can do is audit a city and, after the fact, separate debris that stayed in its footprint from debris that was thrown sideways. That is all. Say the negative out loud and you gain credibility for everything after.

## 6. Six known ways a building falls — and a refusal to guess when it is a seventh

Six mechanisms, each with a published void geometry and a published fatality rate. We do not train a classifier — there is no labelled rubble dataset on earth to train one on. We do Bayesian model averaging over the six, using structure type, what element was removed, load ratio, debris spread and last-gasp impact count. The discipline is the gate on the right: if no class reaches sixty percent, or the structure type is outside the vocabulary, the system refuses to name a mechanism.

## 7. Mechanism geometry becomes a map of pockets — and a headcount per pocket

Here is the thing doctrine keeps in prose and we keep in numbers. Each mechanism predicts where the pockets physically are. A V-shape puts them at both exterior walls. A lean-to puts one big pocket under the raised end. We turn that into a distribution over six zones, then distribute people across those zones — so the output is a set of pockets with a headcount attached, not a building-level guess.

## 8. Eleven and a half expected trapped — and a clock that falls off a cliff at 24 hours

Occupancy and the clock, chosen together because they multiply. Heads times the chance they were home at half past seven times the fraction of the building that actually came down. That gives expected trapped, spread over pockets as a Poisson mean — which is why one pocket can hold three people rather than a coin flip. Then survival decays. The single most important feature of that curve is the cliff between day one and day two.

## 9. ELSE  =  [  λ  ×  s(t)  ×  d_dig  ÷  effort_h  ]  ×  ( 1 − R )

This is the slide that wins or loses the technical questions, so read the formula slowly. People, times survival at the hour the team would actually arrive, times the chance of finding them, divided by the team-hours it costs, times one minus collapse risk. Because it is divided by effort, it is lives per team-hour — a currency a commander can actually spend. And because s(t) is in it, the ranking changes on its own as the night goes on.

## 10. Nine pockets, ranked, with a clock attached to every one

This is the actual output, unedited. Nine pockets, ranked. Column four is people, column five is survival the moment the casualty was trapped, column six is the chance of finding them by digging. The last column is the wall-clock hour the pocket is expected to be cleared. Point at the bottom two rows — the basement is last and it is reached at hour 17.7, when survival has fallen to almost nothing. That is not a failure of the list; that is the list being honest.

## 11. Our own novelty lost where we expected it to win

This is the slide I would not have guessed. We built a phone-census feature to confirm whether people are inside before committing a team. We tested it against simply digging. Where records exist it LOSES half a life — because an imperfect sensor overrides a good prior. Where records are missing it gains point six. So the census is not the headline. Records are. That inversion is the honest finding, and it is why the data pipeline got built first.

## 12. Ten ways we tried to break our own pipeline — and three times it broke

Nobody expects a student team to attack its own system. Do it and you own the room. Ten adversarial tests, all passing. Then the three bugs they caught — the unit bug is the best story, because the first brief printed a plan with an empty ETA column and I nearly shipped it. Say that plainly. Judges reward the person who found their own error.

## 13. How this pipeline lies to you — printed at the end of every run

Same discipline, taken further: here is how the pipeline lies. Zone priors are expert fiat. The collapse fraction constants are invented. The survival curve has four anchors from one study. And the worst one — the Satya Niketan case was tuned toward the published casualty count, so that match validates nothing. I would rather say that than have someone find it.

## 14. What we do not claim — the slide that survives cross-examination

Read the left column slowly. Each line is a thing a rival deck will claim and we will not. This is the slide that survives cross-examination, because a judge cannot catch you overclaiming on something you explicitly refused to claim. Then pivot right: what we do claim is narrower and defensible.

## 15. Five minutes, three beats — and it degrades honestly

Close on feasibility. Three beats, five minutes, no hardware. Then the build order. The last beat is the one to dwell on: take away the records and the plan gets worse, and the system says so. A demo that degrades honestly is more convincing than one that looks perfect on a single nice case.

## 16. where to start.

Land it in three sentences and stop. The first is the problem in the language of the person who has to make the decision. The second is the mechanism of the win. The third is the honesty, which is what makes the first two believable. Do not thank anyone, do not trail off into 'and we also had a landslide module'. Stop.
