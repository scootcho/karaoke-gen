for context: @README.md  @docs/ARCHITECTURE.md @docs/MODAL-MIGRATION.md 

the modal web version of this is live on https://gen.nomadkaraoke.com/ , but it's not yet ready for use by customers.

there are several issues with this which need to be resolved, and I'm a bit overwhelmed by it all so would like your help breaking this down and figuring out a step by step plan to resolve the issues.

the way we architected and built the web version of this, currently deployed on modal, was flawed in several ways. 

1) all elements of the frontend and backend are served from Modal. while Modal is great for easily deploying and running stuff using GPUs, we should probably be serving the frontend from something better suited to static sites, e.g. cloudflare pages.

2) the backend code for everything running on modal was all lumped together in one huge (7000+ lines!) file "app.py" in the repo root: @app.py  
That's an absolute nightmare for maintainability, and I suspect there is a ton of redundant and duplicate code throughout all that too. I have no confidence that the code in there is well tested, high quality, or even makes sense, as it was never built in a modular, maintainable, SOLID way.

3) similarly, the frontend code for the entire web UI version of this was built in a very naive way with basic html/css/js with all of the logic inside a single huge (8000 lines!) javascript file frontend/app.js: @frontend/app.js  
This is awful for maintainability, and again I have no confidence any of it is actually sustainable, maintainable, and there are no tests.

4) the initial tenet of using Modal for this was that it was supposed to be well suited to running GPU workloads (as the audio separation part of the karaoke generation workflow runs much faster with GPU available). However, in practice I saw a bunch of issues when trying to actually use it, e.g. if I tried to run multiple karaoke generation jobs concurrently, inputs would somehow get mixed up and everything became slow and barely usable (e.g. the web interface no longer responded, since it was also served from modal). 

I think we should re-think the architecture so we're not using Modal for everything. We can probably still use it for the audio separation specifically (audio-separator is deployed on modal independently and separation jobs can be executed remotely using the client; details here: https://github.com/nomadkaraoke/python-audio-separator/blob/main/audio_separator/remote/README.md ), but I think we ought to recreate the frontend as a React app, deployed as a static site on Cloudflare pages.
I'd like the bulk of the backend processing (e.g. job processing, video rendering which needs CPU power but not GPU) should be hosted on google cloud, as I have a bunch of google cloud credits available.

I'd also really like to ensure we don't duplicate any code between the karaoke-gen CLI tool vs. this cloud-hosted, web based version. In the version which is currently deployed on Modal, I believe there's duplication of some of the functionality. Where possible, in this new version, I'd rather we rework karaoke-gen so it can be used as a CLI tool and as part of the web based system backend rather than duplicating any functionality.

Please investigate all of the existing code and help make a plan for the new approach to a web-based karaoke-gen.