-- Before citeproc: split [@a; @b] into separate citations, so each can link to its own DOI
-- afterwards (the lab style puts "; " between them anyway).
function Cite(el)
  if #el.citations < 2 then return nil end
  local out = {}
  for i, c in ipairs(el.citations) do
    if i > 1 then
      table.insert(out, pandoc.Str(";"))
      table.insert(out, pandoc.Space())
    end
    table.insert(out, pandoc.Cite({pandoc.Str("@" .. c.id)}, {c}))
  end
  return out
end
