
TOPTARGETS := all clean
SUBDIRS := cases/DischargeInception/Rod/ cases/ItoKMC/StreamerIntegralCriterion/

$(TOPTARGETS): $(SUBDIRS)

$(SUBDIRS): | discharge-lib
	$(MAKE) -C $@ $(MAKECMDGOALS)

discharge-lib:
	$(MAKE) --directory=$(DISCHARGE_HOME) discharge-lib

.PHONY: $(TOPTARGETS) $(SUBDIRS) discharge-lib

