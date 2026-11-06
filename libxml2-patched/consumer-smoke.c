#include <librsvg/rsvg.h>
#include <gdk-pixbuf/gdk-pixbuf.h>
#include <libxml/parser.h>
#include <cairo.h>
#include <stdio.h>
#include <string.h>

int main(void) {
    const char *svg = "<svg xmlns='http://www.w3.org/2000/svg' width='80' height='40'><rect width='80' height='40' fill='green'/><text x='4' y='24'>Test</text></svg>";
    const char *xml = "<!DOCTYPE root [<!ENTITY label 'compatible'>]><root>&label;</root>";
    GError *error = NULL;
    xmlDocPtr doc = xmlReadMemory(xml, (int)strlen(xml), "local.xml", NULL, XML_PARSE_NONET | XML_PARSE_NOENT);
    if (!doc) return 1;
    xmlChar *text = xmlNodeGetContent(xmlDocGetRootElement(doc));
    int correct = text && !xmlStrcmp(text, BAD_CAST "compatible");
    xmlFree(text); xmlFreeDoc(doc);
    if (!correct) return 2;
    puts("PASS old-header libxml2 DOM and ordinary internal entity");
    RsvgHandle *handle = rsvg_handle_new_from_data((const guint8 *)svg, strlen(svg), &error);
    if (!handle) { fprintf(stderr, "SVG load failed\n"); return 3; }
    cairo_surface_t *surface = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, 80, 40);
    cairo_t *cr = cairo_create(surface);
    RsvgRectangle viewport = {0, 0, 80, 40};
    if (!rsvg_handle_render_document(handle, cr, &viewport, &error)) return 4;
    if (cairo_status(cr) != CAIRO_STATUS_SUCCESS) return 5;
    cairo_destroy(cr); cairo_surface_destroy(surface); g_object_unref(handle);
    puts("PASS installed librsvg render with existing consumer binary");
    gboolean has_svg = FALSE;
    GSList *formats = gdk_pixbuf_get_formats();
    for (GSList *entry = formats; entry; entry = entry->next) {
        char *name = gdk_pixbuf_format_get_name(entry->data);
        if (!strcmp(name, "svg")) has_svg = TRUE;
        g_free(name);
    }
    g_slist_free(formats);
    if (has_svg) {
        GInputStream *stream = g_memory_input_stream_new_from_data(svg, strlen(svg), NULL);
        GdkPixbuf *pixbuf = gdk_pixbuf_new_from_stream(stream, NULL, &error);
        if (!pixbuf || gdk_pixbuf_get_width(pixbuf) != 80 || gdk_pixbuf_get_height(pixbuf) != 40) {
            fprintf(stderr, "Installed SVG loader failed: %s\n", error ? error->message : "invalid dimensions");
            return 6;
        }
        g_object_unref(pixbuf); g_object_unref(stream);
        puts("PASS actual GdkPixbuf SVG loader");
    } else {
        puts("NOT PRESENT optional GdkPixbuf SVG loader; direct librsvg render tested above");
    }
    const char *bad = "<svg xmlns='http://www.w3.org/2000/svg'><g></svg>";
    error = NULL;
    handle = rsvg_handle_new_from_data((const guint8 *)bad, strlen(bad), &error);
    if (handle || !error) return 7;
    g_error_free(error);
    puts("PASS malformed SVG returns an ordinary error");
    return 0;
}
