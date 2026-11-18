# NN4PDEs numerical reference fixtures

These tiny synthetic arrays test the Canopy adapter against the original standalone AI4SWE Linear timestep loop. They contain no real geography or measured observations. [reference.json](reference.json) records the upstream revision, source hash, CPU environment, cases, step counts and fixture hashes.

`generate_reference.py` imports no Canopy driver. It executes the original numerical initialization, complete `AI4SWE` class and complete `with torch.no_grad()` timestep block from the pinned source. Case-only assignments set grid shape, spacing, timestep and number of steps. Synthetic terrain, initial water and rainfall replace Carlisle file I/O; output CSV code remains unreachable before 900 seconds. The original two outer passes, inner iterations and convergence check are unedited. Native u/v are stored without applying Canopy's ENU conversion.

The cases cover dry terrain with a raised building and wet asymmetric terrain, at different spacings and timesteps. References contain the states after 1, 7 and 20 steps. The unit tests compare water depth and both velocity components, check the kernel's derivative signs independently and verify state isolation between instances.

Regenerate only after reviewing the pinned upstream revision or an intentional fixture change:

```sh
python model/tests/fixtures/nn4pdes/generate_reference.py
python -m unittest discover -s model/tests -p 'test_nn4pdes.py' -v
```

CPU parity on these cases is a regression check, not a reproduction of the Carlisle paper or a validation of the full London domain. Do not weaken the comparison or alter the vendored equations to hide a discrepancy.
