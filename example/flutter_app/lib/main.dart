import 'package:flutter/material.dart';
import 'sagnos/sagnos_client.dart';
import 'sagnos/models.dart';
import 'sagnos/sagnos_exception.dart';

void main() => runApp(const MyApp());

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Sagnos Demo',
      theme: ThemeData(colorSchemeSeed: Colors.indigo),
      home: const HomePage(),
    );
  }
}

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  // This is the ENTIRE Flutter side — just one client object
  final client = SagnosClient(baseUrl: 'http://127.0.0.1:8000');

  List<User> users = [];
  String status = 'Press a button';
  bool loading = false;

  // Get all users from Python
  Future<void> loadUsers() async {
    setState(() {
      loading = true;
      status = 'Loading...';
    });
    try {
      final result = await client.listUsers();
      setState(() {
        users = result;
        status = '${result.length} users loaded';
      });
    } on SagnosException catch (e) {
      setState(() {
        status = 'Error: ${e.message}';
      });
    } finally {
      setState(() {
        loading = false;
      });
    }
  }

  // Create a user in Python
  Future<void> createUser() async {
    setState(() {
      loading = true;
    });
    try {
      final user = await client.createUser(
        'New User ${users.length + 3}',
        'user${users.length + 3}@test.com',
      );
      setState(() {
        users.add(user);
        status = 'Created: ${user.name}';
      });
    } on SagnosException catch (e) {
      setState(() {
        status = 'Error: ${e.message}';
      });
    } finally {
      setState(() {
        loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('🐍 Sagnos Demo'),
        backgroundColor: Colors.indigo,
        foregroundColor: Colors.white,
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            // Status bar
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.indigo.shade50,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(status, style: const TextStyle(fontSize: 14)),
            ),

            const SizedBox(height: 16),

            // Buttons
            Row(
              children: [
                ElevatedButton.icon(
                  onPressed: loading ? null : loadUsers,
                  icon: const Icon(Icons.download),
                  label: const Text('Load Users'),
                ),
                const SizedBox(width: 12),
                ElevatedButton.icon(
                  onPressed: loading ? null : createUser,
                  icon: const Icon(Icons.add),
                  label: const Text('Create User'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.green,
                    foregroundColor: Colors.white,
                  ),
                ),
              ],
            ),

            const SizedBox(height: 16),

            // User list
            Expanded(
              child: loading
                  ? const Center(child: CircularProgressIndicator())
                  : users.isEmpty
                  ? const Center(child: Text('No users yet — press Load Users'))
                  : ListView.builder(
                      itemCount: users.length,
                      itemBuilder: (context, index) {
                        final user = users[index];
                        return Card(
                          child: ListTile(
                            leading: CircleAvatar(
                              backgroundColor: Colors.indigo,
                              child: Text(
                                user.name[0],
                                style: const TextStyle(color: Colors.white),
                              ),
                            ),
                            title: Text(user.name),
                            subtitle: Text(user.email),
                            trailing: Text('#${user.id}'),
                          ),
                        );
                      },
                    ),
            ),
          ],
        ),
      ),
    );
  }
}
