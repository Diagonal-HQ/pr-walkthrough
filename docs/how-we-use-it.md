# How Diagonal uses PR videos

Our shipping workflow asks the agent to validate a change, record a narrated walkthrough, and link it near the top of the PR description.

Product changes get a recording of the running app. Changes without a useful visible surface get a before-and-after code explanation from git. The video is a handoff artifact: it shows the behavior the reviewer is about to assess.

The agent writes the script, generates narration, captures the flow, renders the edit, and inspects review images. Narration comes first so each action has enough time for its explanation. The output includes a 1080p MP4, captions, transcript, and review evidence.

At Diagonal, final videos go to R2 through our PR asset uploader. The shipping workflow links the public URL. Video files do not enter the source repository. If recording fails, the agent records why and continues the shipping workflow.

This repository replaces our login and Laravel seed code with project hooks. It adds free local narration and optional publishing. Playwright directly owns isolated recording browsers, so our browser session wrapper is not needed.

For another project, use the skill, narration-driven capture, render/review tools, and a short instruction in your shipping workflow. You do not need our issue tracker, app framework, or deployment process.
