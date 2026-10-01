-- Export an already-open Keynote document to PDF and PPTX, then close it without saving.
-- The document is opened beforehand with `open -a Keynote <file>` (Launch Services),
-- because Keynote refuses some files when they arrive via AppleScript's `open`.
-- Usage: osascript keynote_export.applescript <document name> <out.pdf> <out.pptx>
on run argv
	set docName to item 1 of argv
	set pdfPath to item 2 of argv
	set pptxPath to item 3 of argv
	tell application "Keynote"
		set theDoc to document docName
		with timeout of 900 seconds
			export theDoc to (POSIX file pdfPath) as PDF with properties {PDF image quality:Better, all stages:false, skipped slides:false}
			export theDoc to (POSIX file pptxPath) as Microsoft PowerPoint with properties {skipped slides:false, all stages:false}
		end timeout
		close theDoc saving no
	end tell
	return "ok"
end run
