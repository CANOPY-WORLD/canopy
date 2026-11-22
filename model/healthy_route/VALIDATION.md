# Integration validation

The previous evidence for `ad3ceec017be266431ca6677af25adcc7e696b73` did not establish a reproducible Git checkout: the local scaler used CRLF bytes while Git stored LF. The reported clean copy copied working-tree bytes and missed this defect. That evidence is superseded; checksum enforcement remains enabled.

The correction pins packaged JSON to LF in `.gitattributes` and regenerates the scaler hash from its committed bytes. Updated validation is being performed on an actual fresh checkout after merging upstream `abd774b24d065d421022ef5251f596cb7ffa7d6c`. Exact revision, environment and results will be recorded after the checks complete.
