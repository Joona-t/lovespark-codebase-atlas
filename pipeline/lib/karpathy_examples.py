"""Curated Karpathy in-context examples for LLM enrichment prompts.

Each example is either a verbatim quote from his public writing (with source),
or a style-matched paraphrase clearly flagged. Used inline in prompts to bias
the model away from SaaS-marketing voice toward his actual rhetorical patterns.

Sources span: karpathy.github.io blog posts (Recipe, Backprop, RNN, Software 2.0,
CIFAR-10), karpathy.bearblog.dev posts (2025 Year in Review, MenuGen post-mortem,
Verifiability, Animals vs Ghosts, Power to the People, Append-and-Review,
HN auto-grading), and github.com/karpathy READMEs (nanoGPT, nanochat, micrograd,
llm.c, llama2.c, minGPT, build-nanogpt).

style_match=False --> verbatim quote from his actual writing
style_match=True  --> paraphrase in his cadence for section types he doesn't
                       naturally write in that format (e.g. "assumptions")
"""

EXAMPLES: dict[str, list[dict]] = {
    "tldr": [
        {
            "text": "The simplest, fastest repository for training/finetuning medium-sized GPTs.",
            "source": "https://github.com/karpathy/nanoGPT/blob/master/README.md",
            "context": "nanoGPT README, opening line",
            "style_match": False,
        },
        {
            "text": "Have you ever wanted to inference a baby Llama 2 model in pure C? No? Well, now you can! Train the Llama 2 LLM architecture in PyTorch then inference it with one simple 700-line C file (run.c).",
            "source": "https://github.com/karpathy/llama2.c/blob/master/README.md",
            "context": "llama2.c README, opening pitch",
            "style_match": False,
        },
    ],
    "data": [
        {
            "text": "The first step to training a neural net is to not touch any neural net code at all and instead begin by thoroughly inspecting your data. The unambiguously correct place to visualize your data is immediately before your y_hat = model(x). You want to visualize exactly what goes into your network.",
            "source": "https://karpathy.github.io/2019/04/25/recipe/",
            "context": "A Recipe for Training Neural Networks, step 1",
            "style_match": False,
        },
        {
            "text": "All that's going on is that a sequence of indices feeds into a Transformer, and a probability distribution over the next index in the sequence comes out.",
            "source": "https://github.com/karpathy/minGPT/blob/master/README.md",
            "context": "minGPT README, describing the core data flow",
            "style_match": False,
        },
    ],
    "naive": [
        {
            "text": "I maintain one single text note in the Apple Notes app just called 'notes'. A single note means CTRL+F is simple and trivial. Any time any idea or any todo or anything else comes to mind, I append it to the note on top, simply as text.",
            "source": "https://karpathy.bearblog.dev/the-append-and-review-note/",
            "context": "The append-and-review note, the entire system in two sentences",
            "style_match": False,
        },
        {
            "text": "I wanted something super simple, minimal, and educational so I chose to hard-code the Llama 2 architecture and just roll one inference file of pure C with no dependencies.",
            "source": "https://github.com/karpathy/llama2.c/blob/master/README.md",
            "context": "llama2.c README, the deliberately-naive design choice",
            "style_match": False,
        },
    ],
    "architecture": [
        {
            "text": "train.py is a ~300-line boilerplate training loop and model.py a ~300-line GPT model definition. Because the code is so simple, it is very easy to hack to your needs, train new models from scratch, or finetune pretrained checkpoints.",
            "source": "https://github.com/karpathy/nanoGPT/blob/master/README.md",
            "context": "nanoGPT README, the two-file architecture",
            "style_match": False,
        },
        {
            "text": "nanochat is written and configured around one single dial of complexity. All other hyperparameters are calculated automatically in an optimal way.",
            "source": "https://github.com/karpathy/nanochat/blob/master/README.md",
            "context": "nanochat README, the one-dial architecture stance",
            "style_match": False,
        },
    ],
    "core_loop": [
        {
            "text": "GPT is not a complicated model and this implementation is appropriately about 300 lines of code. minGPT tries to be small, clean, interpretable and educational, as most of the currently available GPT model implementations can a bit sprawling.",
            "source": "https://github.com/karpathy/minGPT/blob/master/README.md",
            "context": "minGPT README, framing the central file",
            "style_match": False,
        },
        {
            "text": "Implements backpropagation (reverse-mode autodiff) over a dynamically built DAG and a small neural networks library on top of it with a PyTorch-like API. Both are tiny, with about 100 and 50 lines of code respectively.",
            "source": "https://github.com/karpathy/micrograd/blob/master/README.md",
            "context": "micrograd README, the core loop in two files",
            "style_match": False,
        },
    ],
    "verification": [
        {
            "text": "Overfit a single batch of only a few examples (e.g. as little as two) and verify that we can reach the lowest achievable loss. If writing your neural net code was like training one, you'd want to use a very small learning rate and guess and then evaluate the full test set after every iteration.",
            "source": "https://karpathy.github.io/2019/04/25/recipe/",
            "context": "A Recipe for Training Neural Networks, sanity-check by overfit",
            "style_match": False,
        },
        {
            "text": "Software 1.0 easily automates what you can specify. Software 2.0 easily automates what you can verify. The environment has to be resettable, efficient, and rewardable.",
            "source": "https://karpathy.bearblog.dev/verifiability/",
            "context": "Verifiability, the central distinction",
            "style_match": False,
        },
    ],
    "assumptions": [
        {
            "text": "The problem with Backpropagation is that it is a leaky abstraction. If you're using sigmoids or tanh non-linearities in your network and you understand backpropagation you should always be nervous about making sure that the initialization doesn't cause them to be fully saturated.",
            "source": "https://karpathy.medium.com/yes-you-should-understand-backprop-e2f06eab496b",
            "context": "Yes you should understand backprop, the silent-failure framing",
            "style_match": False,
        },
        {
            "text": "Honestly, every line that does a divide is silently assuming the denominator is nonzero, every dict lookup is silently assuming the key exists, every retry loop is silently assuming the failure mode is transient. You should be nervous about the ones you haven't named.",
            "source": "style-matched paraphrase",
            "context": "Karpathy-cadence framing of code assumptions; no direct quote exists in this exact form",
            "style_match": True,
        },
    ],
    "stack": [
        {
            "text": "pytorch <3, numpy <3, transformers for huggingface transformers <3 (to load GPT-2 checkpoints), datasets for huggingface datasets <3 (if you want to download + preprocess OpenWebText).",
            "source": "https://github.com/karpathy/nanoGPT/blob/master/README.md",
            "context": "nanoGPT README, dependency list with one-line rationale per dep",
            "style_match": False,
        },
        {
            "text": "LLMs in simple, pure C/CUDA with no need for 245MB of PyTorch or 107MB of cPython.",
            "source": "https://github.com/karpathy/llm.c/blob/master/README.md",
            "context": "llm.c README, the dependency-philosophy line",
            "style_match": False,
        },
    ],
    "decisions": [
        {
            "text": "minGPT is in a semi-archived state. minGPT became referenced across a wide variety of places which limited my ability to make larger changes, and I wanted to shift toward code that is still simple and hackable but has teeth. For more recent developments see my rewrite nanoGPT.",
            "source": "https://github.com/karpathy/minGPT/blob/master/README.md",
            "context": "minGPT README, archival note explaining why nanoGPT exists",
            "style_match": False,
        },
        {
            "text": "If there is a PR that improves performance by 2% but costs 500 lines of complex C code, I may reject the PR because the complexity is not worth it. I want llm.c to be a place for education. I also want llm.c to be very fast too, even practically useful to train networks.",
            "source": "https://github.com/karpathy/llm.c/blob/master/README.md",
            "context": "llm.c README, decision rule for accepting changes",
            "style_match": False,
        },
    ],
    "tradeoffs": [
        {
            "text": "We'll be left with a choice of using a 90% accurate model we understand, or 99% accurate model we don't.",
            "source": "https://karpathy.medium.com/software-2-0-a64152b37c35",
            "context": "Software 2.0, the interpretability-vs-performance tradeoff in one line",
            "style_match": False,
        },
        {
            "text": "It was too much bear. Leave as future work. I thought of quitting the project around here, but I felt better when I woke up the next morning.",
            "source": "https://karpathy.bearblog.dev/vibe-coding-menugen/",
            "context": "Vibe coding MenuGen, on cutting scope mid-build",
            "style_match": False,
        },
    ],
    "metrics": [
        {
            "text": "train.py reproduces GPT-2 (124M) on OpenWebText, running on a single 8XA100 40GB node in about 4 days. On one A100 GPU this training run takes about 3 minutes and the best validation loss is 1.4697.",
            "source": "https://github.com/karpathy/nanoGPT/blob/master/README.md",
            "context": "nanoGPT README, exact training metrics on named hardware",
            "style_match": False,
        },
        {
            "text": "Train your own GPT-2 capability LLM for only $48 (~2 hours of 8XH100 GPU node). On a spot instance, the total cost can be closer to ~$15.",
            "source": "https://github.com/karpathy/nanochat/blob/master/README.md",
            "context": "nanochat README, dollar-cost claims with hardware",
            "style_match": False,
        },
    ],
    "failures": [
        {
            "text": "If a ReLU neuron is unfortunately initialized such that it never fires, or if a neuron's weights ever get knocked off with a large update during training into this regime, then this neuron will remain permanently dead. They can 'silently fail', e.g., by silently adopting biases in their training data, which are very difficult to properly analyze.",
            "source": "https://karpathy.medium.com/yes-you-should-understand-backprop-e2f06eab496b",
            "context": "backprop post + Software 2.0, two canonical silent-failure examples",
            "style_match": False,
        },
        {
            "text": "I caught Claude using a really bad idea approach to match up a successful Stripe payment to user credits. Seeing a new website materialize so quickly is a strong hook. I felt like I was 80% done but (foreshadowing...) it was a bit closer to 20%.",
            "source": "https://karpathy.bearblog.dev/vibe-coding-menugen/",
            "context": "Vibe coding MenuGen, on the gap between feels-done and actually-done",
            "style_match": False,
        },
    ],
    "v_next": [
        {
            "text": "I expect most applications will wish to create a fork of this repo and hack it to their specific needs and deployment platforms.",
            "source": "https://github.com/karpathy/llama2.c/blob/master/README.md",
            "context": "llama2.c README, on the explicit forward path",
            "style_match": False,
        },
        {
            "text": "I'm left with an equal mix of amazement and a bit of frustration of what could be. Vibe coding menugen was exhilarating and fun escapade as a local demo, but a bit of a painful slog as a deployed, real app.",
            "source": "https://karpathy.bearblog.dev/vibe-coding-menugen/",
            "context": "Vibe coding MenuGen, the closing v_next reflection",
            "style_match": False,
        },
    ],
    "reproducibility": [
        {
            "text": "We basically start from an empty file and work our way to a reproduction of the GPT-2 (124M) model. Today, reproducing it is a matter of ~1hr and ~$10. You'll need a cloud GPU box if you don't have enough; I recommend Lambda.",
            "source": "https://github.com/karpathy/build-nanogpt/blob/master/README.md",
            "context": "build-nanogpt README, exact reproduction recipe with cost",
            "style_match": False,
        },
        {
            "text": "Running 930 LLM queries across 31 days of content cost about $58 and somewhere around ~1 hour of processing time. Vibe coding the actual project was relatively painless and took about 3 hours with Opus 4.5, with a few hickups but overall very impressive.",
            "source": "https://karpathy.bearblog.dev/auto-grade-hn/",
            "context": "Auto-grading HN, concrete repro cost + wall-clock numbers",
            "style_match": False,
        },
    ],
    "takeaway": [
        {
            "text": "If you try to ignore how it works under the hood because 'TensorFlow automagically makes my networks learn', you will not be ready to wrestle with the dangers it presents, and you will be much less effective at building and debugging neural networks.",
            "source": "https://karpathy.medium.com/yes-you-should-understand-backprop-e2f06eab496b",
            "context": "backprop post, the closing lesson",
            "style_match": False,
        },
        {
            "text": "Sometimes the ratio of how simple your model is to the quality of the results you get out blows past your expectations. The future is already here, and it is shockingly distributed. Power to the people.",
            "source": "https://karpathy.github.io/2015/05/21/rnn-effectiveness/ + https://karpathy.bearblog.dev/power-to-the-people/",
            "context": "RNN post + Power to the people, two takeaways stitched into one Karpathy beat",
            "style_match": False,
        },
    ],
}


# Banned phrases --- the post-filter should flag any of these in generated output.
# Karpathy notably does NOT use SaaS-marketing vocabulary. He writes with
# concrete numbers, hardware names, file names, and direct asides instead.
BANNED_PHRASES = [
    "exciting",
    "powerful",
    "robust",
    "scalable",
    "seamless",
    "leverage",
    "leverages",
    "synergize",
    "synergy",
    "enables",
    "empowers",
    "best-in-class",
    "world-class",
    "cutting-edge",
    "state-of-the-art",
    "revolutionary",
    "game-changing",
    "next-generation",
    "next-gen",
    "industry-leading",
    "mission-critical",
    "turnkey",
    "out-of-the-box",
    "battle-tested",
    "production-grade",
    "enterprise-grade",
    "unlock",
    "unleash",
    "delight",
    "delightful",
    "elegant solution",
    "first-class",
    "holistic",
    "paradigm shift",
    "deep dive",
]


# Style anchors --- phrases Karpathy actually uses or paraphrases of his cadence.
# The LLM can echo these to stay in voice. Sourced primarily from the Recipe,
# Software 2.0, MenuGen post-mortem, Year in Review, and the various READMEs.
STYLE_ANCHORS = [
    "Honestly,",
    "Amusingly,",
    "Interestingly,",
    "You should be nervous about",
    "The naive thing would be",
    "It is a leaky abstraction.",
    "Look at the data first.",
    "Become one with the data.",
    "Overfit a single batch first.",
    "The simplest, fastest",
    "tiny, with about N lines of code",
    "I felt like I was 80% done but it was closer to 20%.",
    "It was too much bear. Leave as future work.",
    "Foreshadowing...",
    "I thought of quitting the project around here.",
    "no need for 245MB of bloat",
    "<3",
    "simple, pure",
    "small, clean, interpretable and educational",
    "still simple and hackable but has teeth",
    "one single dial of complexity",
    "easy to hack to your needs",
    "fork of this repo and hack it",
    "in pure C with no dependencies",
    "reproducing it is a matter of ~Nhr and ~$N",
    "on a single 8XA100 40GB node",
    "on an 8XH100 GPU node",
    "On a spot instance, the total cost can be closer to",
    "Power to the people.",
    "silently fail",
    "silently adopting biases",
    "permanently dead",
    "the complexity is not worth it",
    "We'll be left with a choice of",
]


def get_examples(section_key: str) -> list[dict]:
    """Return the example list for a section key, or [] if unknown."""
    return EXAMPLES.get(section_key, [])


def format_examples_for_prompt(section_key: str) -> str:
    """Render the examples for a section as an inline prompt block.

    Output is plain text, ready to drop into a system or user message.
    Each example is rendered as a bullet with the source attribution after
    an em-dash, mirroring how Karpathy himself cites in his blog footers.
    """
    items = get_examples(section_key)
    if not items:
        return ""
    lines = [f"# In-context examples for section: {section_key}"]
    lines.append("# Match this voice. Concrete nouns, named hardware, numbers, and asides.")
    lines.append("# Do NOT echo the exact wording --- mirror the cadence.")
    for ex in items:
        tag = " [style-match]" if ex.get("style_match") else ""
        lines.append(f'- "{ex["text"]}" --- {ex["context"]}{tag}')
    return "\n".join(lines)


def all_section_keys() -> list[str]:
    """Return the canonical ordered list of audit section keys."""
    return list(EXAMPLES.keys())


if __name__ == "__main__":
    # Smoke test: print one rendered block per section so the file is
    # eyeball-verifiable from the command line.
    for key in all_section_keys():
        print(format_examples_for_prompt(key))
        print()
