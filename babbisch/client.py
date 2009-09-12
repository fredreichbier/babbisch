class ObjectVisitor(object):
    def visit_objects(self, objects):
        for tag, obj in objects.iteritems():
            self.visit(obj)

    def generic_visit(self, obj):
        pass

    def visit(self, obj):
        visitor_name = 'visit_%s' % obj['class']
        return getattr(self, visitor_name, self.generic_visit)(obj)
