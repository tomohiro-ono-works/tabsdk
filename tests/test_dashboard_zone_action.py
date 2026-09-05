from twbpatch import TwbWorkbook


def _write_dashboard_metadata_workbook(tmp_path):
    twb = tmp_path / "dashboard_metadata.twb"
    twb.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <worksheets>
    <worksheet name="Source" caption="Source Sheet" />
    <worksheet name="Target" caption="Target Sheet" />
  </worksheets>
  <dashboards>
    <dashboard name="Dashboard1" caption="Overview">
      <size sizing-mode="fixed" minwidth="1000" maxwidth="1000" minheight="800" maxheight="800" />
      <zones>
        <zone id="1" type-v2="layout-basic" x="0" y="0" w="100000" h="100000">
          <zone id="2" name="Source" x="12500" y="25000" w="50000" h="37500" show-title="true" />
          <zone id="3" type-v2="text" x="62500" y="25000" w="25000" h="12500">
            <formatted-text><run>Hello dashboard</run></formatted-text>
          </zone>
          <zone id="4" name="Target" x="62500" y="37500" w="25000" h="25000" />
        </zone>
      </zones>
      <devicelayouts>
        <devicelayout name="phone">
          <size sizing-mode="fixed" minwidth="400" maxwidth="400" minheight="700" maxheight="700" />
          <zones>
            <zone id="phone-1" name="Source" x="0" y="10000" w="100000" h="50000" />
          </zones>
        </devicelayout>
      </devicelayouts>
    </dashboard>
    <dashboard name="Responsive">
      <size sizing-mode="automatic" />
      <zones>
        <zone id="responsive-1" type-v2="text" x="10000" y="20000" w="30000" h="40000" />
      </zones>
    </dashboard>
  </dashboards>
  <actions>
    <action name="[Action].[Filter Orders]" caption="Filter Orders">
      <activation type="on-select" />
      <source dashboard="Dashboard1" type="sheet">
        <exclude-sheet name="Target" />
      </source>
      <command command="filter">
        <target dashboard="Dashboard1" type="sheet">
          <exclude-sheet name="Source" />
        </target>
        <link expression="[ds1].[Region]" />
        <param name="selection" value="all" />
      </command>
    </action>
  </actions>
</workbook>
""",
        encoding="utf-8",
    )
    return twb


def test_list_dashboard_zones_returns_raw_and_pixel_coordinates(tmp_path):
    wb = TwbWorkbook.open(str(_write_dashboard_metadata_workbook(tmp_path)))

    zones = wb.list_dashboard_zones("Overview")

    assert [zone.id for zone in zones] == ["1", "2", "3", "4"]
    worksheet = next(zone for zone in zones if zone.id == "2")
    assert worksheet.parent_id == "1"
    assert worksheet.depth == 1
    assert worksheet.type == "worksheet"
    assert worksheet.worksheet == "Source Sheet"
    assert worksheet.worksheet_id == "Source"
    assert worksheet.dashboard_width_px == 1000
    assert worksheet.dashboard_height_px == 800
    assert (worksheet.x_raw, worksheet.x_px) == (12500, 125)
    assert (worksheet.y_raw, worksheet.y_px) == (25000, 200)
    assert (worksheet.width_raw, worksheet.width_px) == (50000, 500)
    assert (worksheet.height_raw, worksheet.height_px) == (37500, 300)
    assert worksheet.show_title is True

    text = next(zone for zone in zones if zone.id == "3")
    assert text.text == "Hello dashboard"
    assert wb.get_dashboard("Overview").zones == zones


def test_list_dashboard_zones_handles_device_and_responsive_layouts(tmp_path):
    wb = TwbWorkbook.open(str(_write_dashboard_metadata_workbook(tmp_path)))

    all_zones = wb.list_dashboard_zones("Overview", include_device_layouts=True)
    phone = next(zone for zone in all_zones if zone.id == "phone-1")
    assert phone.layout == "phone"
    assert (phone.x_px, phone.y_px, phone.width_px, phone.height_px) == (0, 70, 400, 350)

    responsive = wb.list_dashboard_zones("Responsive")[0]
    assert responsive.sizing_mode == "automatic"
    assert responsive.x_px is None
    assert responsive.width_px is None

    converted = wb.list_dashboard_zones("Responsive", width_px=1200, height_px=900)[0]
    assert (converted.x_px, converted.y_px, converted.width_px, converted.height_px) == (120, 180, 360, 360)


def test_list_dashboard_actions_resolves_source_target_and_command(tmp_path):
    wb = TwbWorkbook.open(str(_write_dashboard_metadata_workbook(tmp_path)))

    actions = wb.list_dashboard_actions("Overview")

    assert len(actions) == 1
    action = actions[0]
    assert action.id == "[Action].[Filter Orders]"
    assert action.caption == "Filter Orders"
    assert action.type == "filter"
    assert action.activation == "on-select"
    assert action.command == "filter"
    assert action.source_dashboard == "Overview"
    assert action.source_worksheets == ["Source Sheet"]
    assert action.excluded_source_worksheets == ["Target Sheet"]
    assert action.target_dashboard == "Overview"
    assert action.target_worksheets == ["Target Sheet"]
    assert action.excluded_target_worksheets == ["Source Sheet"]
    assert action.links == [{"expression": "[ds1].[Region]"}]
    assert action.params == {"selection": "all"}
    assert action.details["tag"] == "action"
    assert wb.get_dashboard("Overview").actions == actions
