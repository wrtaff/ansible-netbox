# Gmailctl Configuration

`config.jsonnet` is the canonical, Git-tracked definition of Will's Gmail
filters and labels. Gmail is deployed state, not the configuration source.

## Change Workflow

1. Update `config.jsonnet` on an `agent/<host>/<topic>` branch.
2. Copy the candidate file to `gmailctl-ansible` outside the canonical source.
3. Run `sudo /root/go/bin/gmailctl debug --filename <candidate>`.
4. Run `sudo /root/go/bin/gmailctl diff --filename <candidate>` and review the
   full diff. It must contain only the approved filter and label changes.
5. Commit the config change before deployment. Push the branch for hub review.
6. Only after explicit authorization, run `sudo /root/go/bin/gmailctl apply
   --filename <candidate>` and verify a post-apply diff is empty.

## Rebaseline and Drift

When a Gmail filter is changed outside Gmailctl, export the current live state:

```bash
sudo /root/go/bin/gmailctl download --output /tmp/gmailctl-live.jsonnet
```

Copy that export over `config.jsonnet`, review the resulting Git diff, and
commit it before making further managed changes. Use `gmailctl diff` as a
read-only drift check. Do not deploy ignored scratch exports from `pops/tmp/`.

## Known Limitation

Gmailctl currently cannot import filters using the Gmail `ExcludeChats`
criterion. Preserve that live filter and do not apply a config that would
remove or alter it until the tool supports the criterion.
