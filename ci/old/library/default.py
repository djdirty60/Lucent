import sys

if len(sys.argv) > 1 and sys.argv[1] == "widget_refresh":
    import widget
    widget.refresh(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "0")
elif len(sys.argv) > 3 and sys.argv[1] in ("add", "remove"):
    import quick                       # add / remove one title at once: RunScript(script.lucent.library,add,movie,123[,trakt])
    quick.run(sys.argv[1], sys.argv[2], sys.argv[3], len(sys.argv) > 4 and sys.argv[4] == "trakt")
elif len(sys.argv) > 3 and sys.argv[1] == "skip":
    import quick                       # one episode / season out for good: RunScript(script.lucent.library,skip,<show trakt id>,S01E02|S01)
    quick.skip(sys.argv[2], sys.argv[3])
elif len(sys.argv) > 1 and sys.argv[1] in ("status", "update", "surprise", "pushwatched", "nextinset"):
    import tools
    tools.run(sys.argv[1], sys.argv[2:])
else:
    import lib
    lib.run(manual=True)
