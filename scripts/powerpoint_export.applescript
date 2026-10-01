-- Export one PowerPoint file to PDF without touching the original.
-- Usage: osascript powerpoint_export.applescript <in.pptx> <out.pdf>
on run argv
	set inPath to item 1 of argv
	set pdfPath to item 2 of argv
	tell application "Microsoft PowerPoint"
		open (POSIX file inPath)
		set theDoc to active presentation
		with timeout of 600 seconds
			save theDoc in (POSIX file pdfPath) as save as PDF
		end timeout
		close theDoc saving no
	end tell
	return "ok"
end run
