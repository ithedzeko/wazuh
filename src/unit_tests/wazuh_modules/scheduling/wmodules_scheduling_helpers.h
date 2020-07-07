#ifndef __WMODULES_SCHEDULING_HELPERS_H__
#define __WMODULES_SCHEDULING_HELPERS_H__

#include <stdarg.h>
#include <stddef.h>
#include <setjmp.h>
#include <cmocka.h>
#include "shared.h"
#include "wazuh_modules/wmodules.h"

typedef struct test_structure {
    wmodule *module;
    OS_XML xml;
    XML_NODE nodes;
} test_structure;

const XML_NODE string_to_xml_node(const char * string, OS_XML *_lxml);
sched_scan_config init_config_from_string(const char* string);

/* Sets current simulation time */
void set_current_time(time_t _time);

#endif
