import mercurial.node

CFN = '.veh.conf'


def warn_changes(ui, repo, hooktype, **kwargs):
    """hg hook to monitor changes of .veh.conf in pull and update.

    install in hgrc:
    [hooks]
    changegroup.veh=python:veh.hooks.warn_changes
    preupdate.veh=python:veh.hooks.warn_changes

    """
    try:
        if hooktype == 'changegroup':
            warning = "WARNING: .veh.conf has been modified in changesets.\n"
            node = kwargs['node']
    #        if CFN in repo[node].files():
    #            ui.warn(warning)
    #        else:
    #            for ctx in repo[node].descendants():
    #                if CFN in ctx.files():
    #                    ui.warn(warning)
    #                    break
            bnid = mercurial.node.bin(node)
            for rev in xrange(repo.changelog.rev(bnid), len(repo.changelog)):
                ctx = repo[repo.changelog.node(rev)]
                if CFN in ctx.files():
                    ui.warn(warning)
                    break
        elif hooktype == 'preupdate':
            warning = "WARNING: update modifying .veh.conf\n"
            wd = repo[None]
            parent = None
            parent1 = repo[kwargs['parent1']]
            parent2 = kwargs.get('parent2')
            parent2 = parent2 and repo[parent2]
            if parent1.node() not in repo.dirstate.parents():
                parent = parent1
            elif parent2 and parent2 not in repo.dirstate.parents():
                parent = parent2
            if parent:
                if CFN in parent and CFN in wd:
                    if not parent[CFN].cmp(wd[CFN].data()):
                        ui.warn(warning)
                elif CFN not in parent and CFN in wd:
                    ui.warn('WARNING: update removing .veh.conf\n')
                elif CFN in parent and CFN not in wd:
                    ui.warn('WARNING: update adding .veh.conf\n')
    except Exception, e:
        ui.error('whoops! %s' % e)
