"""A soft IOC for the EPICS tests: the example book's source-tune PVs (caproto)."""
from caproto.server import PVGroup, pvproperty, run, template_arg_parser


class Source(PVGroup):
    HV_Offset = pvproperty(value=3000.0, units="V")
    Extract = pvproperty(value=-110.0, units="V")
    Laser_Energy = pvproperty(value=1.2, units="mJ", precision=2)


if __name__ == "__main__":
    parser, split_args = template_arg_parser(default_prefix="SRC:", desc="test IOC")
    ioc_options, run_options = split_args(parser.parse_args())
    run(Source(**ioc_options).pvdb, **run_options)
